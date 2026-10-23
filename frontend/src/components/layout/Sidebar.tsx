import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  TrendingUp,
  Bell,
  Settings,
  BarChart2,
  Cpu,
  ChevronLeft,
  ChevronRight,
  Leaf,
  Lightbulb,
} from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Overview', icon: <LayoutDashboard size={20} /> },
  { to: '/monitoring', label: 'Live Monitoring', icon: <Activity size={20} /> },
  { to: '/predictions', label: 'Predictions', icon: <TrendingUp size={20} /> },
  { to: '/advisory', label: 'Advisor', icon: <Lightbulb size={20} /> },
  { to: '/alerts', label: 'Alerts', icon: <Bell size={20} /> },
  { to: '/automation', label: 'Automation', icon: <Settings size={20} /> },
  { to: '/analytics', label: 'Analytics', icon: <BarChart2 size={20} /> },
  { to: '/devices', label: 'Device Health', icon: <Cpu size={20} /> },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <nav
      style={{
        width: collapsed ? 64 : 240,
        minWidth: collapsed ? 64 : 240,
        background: 'var(--color-sidebar-bg)',
        color: 'var(--color-sidebar-text)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        transition: 'width 0.2s ease, min-width 0.2s ease',
        overflow: 'hidden',
      }}
    >
      {/* Brand */}
      <div
        style={{
          padding: '20px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          minHeight: 60,
        }}
      >
        <Leaf size={24} color="#4ade80" style={{ flexShrink: 0 }} />
        {!collapsed && (
          <span style={{ fontWeight: 700, fontSize: 16, whiteSpace: 'nowrap' }}>
            SolarFlow
          </span>
        )}
      </div>

      {/* Nav links */}
      <div style={{ flex: 1, paddingTop: 8 }}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 16px',
              margin: '2px 8px',
              borderRadius: 6,
              color: isActive ? '#ffffff' : 'var(--color-sidebar-text)',
              background: isActive ? 'var(--color-sidebar-active)' : 'transparent',
              fontWeight: isActive ? 600 : 400,
              fontSize: 14,
              whiteSpace: 'nowrap',
              textDecoration: 'none',
              transition: 'background 0.15s',
            })}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLAnchorElement;
              if (!el.classList.contains('active')) {
                el.style.background = 'var(--color-sidebar-hover)';
              }
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLAnchorElement;
              if (!el.style.background.includes('var(--color-sidebar-active)')) {
                el.style.background = '';
              }
            }}
          >
            <span style={{ flexShrink: 0 }}>{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '12px 16px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
          color: 'var(--color-sidebar-text)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 14,
          gap: 8,
        }}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={18} /> : (
          <>
            <ChevronLeft size={18} />
            <span style={{ whiteSpace: 'nowrap' }}>Collapse</span>
          </>
        )}
      </button>
    </nav>
  );
}
