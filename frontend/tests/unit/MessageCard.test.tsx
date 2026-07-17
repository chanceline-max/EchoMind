import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessageCard } from "../../src/components/MessageCard";
import type { MessageSummary } from "../../src/types/api";

const message: MessageSummary = {
  id: "message-1", conversation_id: "conversation-1", source_message_id: "source-1",
  sender_id: "person-1",
  sender_display_name: "Person A", timestamp: "2026-07-17T00:00:00Z", message_type: "text",
  raw_content: "raw ".repeat(100), normalized_content: "normalized content", source_order: 0,
  reply_to_message_id: null, duplicate_of_message_id: null,
  is_system_message: false, is_recalled_message: false, excluded_from_analysis: false,
  exclusion_reasons: [],
};

describe("MessageCard", () => {
  it("distinguishes raw and normalized plain text and collapses long content", async () => {
    render(<MessageCard message={message} changing={false} onToggleExcluded={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "原始内容" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "规范化内容" })).toBeInTheDocument();
    expect(screen.getByText(/raw raw/).textContent?.endsWith("…")).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "展开全文" }));
    expect(screen.getByRole("heading", { name: "原始内容" }).nextElementSibling?.textContent).toBe(message.raw_content);
    expect(document.querySelector("a[href]")).toBeNull();
  });

  it("uses the database message object when toggling exclusion", async () => {
    const toggle = vi.fn();
    render(<MessageCard message={message} changing={false} onToggleExcluded={toggle} />);
    await userEvent.click(screen.getByRole("button", { name: "排除分析" }));
    expect(toggle).toHaveBeenCalledWith(message);
  });
});
