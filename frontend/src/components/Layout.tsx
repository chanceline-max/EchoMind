import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <NavLink className="brand" to="/">EchoMind</NavLink>
        <nav aria-label="主导航">
          <NavLink to="/import">导入</NavLink>
          <NavLink to="/conversations">会话</NavLink>
          <NavLink to="/insights">Insight 审核</NavLink>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
