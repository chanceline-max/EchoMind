interface Props {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}

export function Pagination({ offset, limit, total, onChange }: Props) {
  return (
    <div className="pagination" aria-label="分页">
      <button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>上一页</button>
      <span>{total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} / {total}</span>
      <button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>下一页</button>
    </div>
  );
}
