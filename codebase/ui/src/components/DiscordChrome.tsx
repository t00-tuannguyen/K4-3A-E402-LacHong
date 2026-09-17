import { Bell, BookOpen, Bot, Hash, Headphones, HelpCircle, Mic, Moon, PanelRightClose, PanelRightOpen, Plus, Settings, Sun, Ticket, Users, Volume2 } from "lucide-react";
import type { ReactNode } from "react";

type DiscordChromeProps = {
  children: ReactNode;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  inspectorOpen: boolean;
  onToggleInspector: () => void;
  inspector: ReactNode;
  activeChannel: "tro-ly-hoi-dap" | "nguon-chinh-thuc";
  onChannelSelect: (channel: "tro-ly-hoi-dap" | "nguon-chinh-thuc") => void;
};

export function DiscordChrome({ children, theme, onToggleTheme, inspectorOpen, onToggleInspector, inspector, activeChannel, onChannelSelect }: DiscordChromeProps) {
  return (
    <div data-theme={theme} className="discord-root flex h-screen overflow-hidden">
      <aside className="discord-server-rail hidden w-[72px] shrink-0 flex-col items-center gap-3 py-3 sm:flex">
        <div className="server-icon rounded-2xl bg-[var(--discord-brand)] font-bold text-white">K4</div>
        <div className="h-0.5 w-8 rounded bg-[var(--discord-bg-hover)]" />
        <div className="server-icon"><BookOpen size={20} /></div>
        <div className="server-icon text-[var(--discord-green)]"><Plus size={24} /></div>
      </aside>

      <aside className="discord-channel-sidebar hidden w-60 shrink-0 flex-col md:flex">
        <div className="flex h-12 items-center border-b border-[var(--discord-bg-tertiary)] px-4 font-semibold text-[var(--discord-text-strong)] shadow-sm">Cộng đồng K4 · L3–4</div>
        <nav className="flex-1 overflow-y-auto p-2">
          <ChannelGroup label="Kênh thông báo">
            <Channel icon={<Bell size={16} />} label="thong-bao-chung" />
            <Channel active={activeChannel === "nguon-chinh-thuc"} onClick={() => onChannelSelect("nguon-chinh-thuc")} icon={<BookOpen size={16} />} label="nguon-chinh-thuc" />
          </ChannelGroup>
          <ChannelGroup label="Hỗ trợ học tập">
            <Channel active={activeChannel === "tro-ly-hoi-dap"} onClick={() => onChannelSelect("tro-ly-hoi-dap")} icon={<Hash size={17} />} label="tro-ly-hoi-dap" />
            <Channel icon={<Ticket size={16} />} label="ticket-support" />
          </ChannelGroup>
          <ChannelGroup label="Kênh thoại">
            <Channel icon={<Volume2 size={16} />} label="phòng-lab-coach" />
          </ChannelGroup>
          <ChannelGroup label="Đang online — 2">
            <OnlineMember color="bg-[#5865f2]" initials="AI" label="Trợ lý K4" bot />
            <OnlineMember color="bg-[#23a559]" initials="TA" label="TA_OnDuty" />
          </ChannelGroup>
        </nav>
        <div className="discord-profile flex h-[52px] items-center gap-2 px-2">
          <Avatar initials="HV" color="bg-[#23a559]" />
          <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-[var(--discord-text-strong)]">Học Viên K4</p><p className="text-[10px] text-[var(--discord-text-faint)]">#2A202602628</p></div>
          <Mic size={15} /><Headphones size={15} /><Settings size={15} />
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="discord-channel-header flex h-12 shrink-0 items-center border-b px-4 shadow-sm">
          <Hash className="mr-2 text-[var(--discord-text-faint)]" size={22} />
          <strong className="text-sm text-[var(--discord-text-strong)]">{activeChannel}</strong>
          <span className="ml-3 hidden border-l border-[var(--discord-border)] pl-3 text-xs text-[var(--discord-text-faint)] lg:block">{activeChannel === "nguon-chinh-thuc" ? "Thông báo và bằng chứng nguồn chính thức" : "Tra cứu quy chế, hạn nộp và thủ tục chính thức"}</span>
          <div className="ml-auto flex items-center gap-4 text-[var(--discord-text-muted)]">
            <button aria-label="Đổi theme" onClick={onToggleTheme}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
            <button aria-label="Ẩn hiện agent inspector" onClick={onToggleInspector}>{inspectorOpen ? <PanelRightClose size={19} /> : <PanelRightOpen size={19} />}</button>
            <Bell size={18} /><Users size={19} /><HelpCircle size={18} />
          </div>
        </header>
        {children}
      </main>

      <aside className="discord-member-sidebar hidden w-60 shrink-0 p-4 xl:block">
        <MemberGroup label="Online — 2">
          <Member initials="AI" name="Trợ lý K4" color="bg-[#5865f2]" bot />
          <Member initials="TA" name="TA_OnDuty" color="bg-[#23a559]" />
        </MemberGroup>
        <MemberGroup label="Offline — 4">
          <Member initials="NT" name="Nguyễn Tiến Tuân" color="bg-[#747f8d]" offline />
          <Member initials="TV" name="Trần Phạm Thái Vũ" color="bg-[#747f8d]" offline />
          <Member initials="VD" name="Vũ Duy Điệp" color="bg-[#747f8d]" offline />
          <Member initials="VH" name="Võ Phú Hãn" color="bg-[#747f8d]" offline />
        </MemberGroup>
      </aside>
      {inspectorOpen && <aside aria-label="Agent inspector" className="agent-inspector-drawer fixed bottom-0 right-0 top-12 z-40 w-[min(380px,90vw)] border-l border-[var(--discord-border)] shadow-2xl">{inspector}</aside>}
    </div>
  );
}

function ChannelGroup({ label, children }: { label: string; children: ReactNode }) {
  return <section className="mb-4"><h2 className="mb-1 px-2 text-[11px] font-bold uppercase tracking-wide text-[var(--discord-text-faint)]">{label}</h2>{children}</section>;
}

function Channel({ icon, label, active, onClick }: { icon: ReactNode; label: string; active?: boolean; onClick?: () => void }) {
  return <button type="button" onClick={onClick} className={`mb-0.5 flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-left text-sm ${active ? "bg-[var(--discord-bg-active)] text-[var(--discord-text-strong)]" : "text-[var(--discord-text-faint)] hover:bg-[var(--discord-bg-hover)] hover:text-[var(--discord-text)]"}`}>{icon}<span>{label}</span></button>;
}

function Avatar({ initials, color }: { initials: string; color: string }) {
  return <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white ${color}`}>{initials}</span>;
}

function OnlineMember({ initials, label, color, bot }: { initials: string; label: string; color: string; bot?: boolean }) {
  return <div className="flex items-center gap-2 px-2 py-1 text-xs text-[var(--discord-text-muted)]"><span className="relative"><Avatar initials={initials} color={color} /><i className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-[var(--discord-bg-secondary)] bg-[var(--discord-green)]" /></span>{label}{bot && <Bot size={12} className="text-[var(--discord-brand)]" />}</div>;
}

function MemberGroup({ label, children }: { label: string; children: ReactNode }) {
  return <section className="mb-6"><h2 className="mb-2 text-[11px] font-bold uppercase text-[var(--discord-text-faint)]">{label}</h2><div className="space-y-2">{children}</div></section>;
}

function Member({ initials, name, color, offline, bot }: { initials: string; name: string; color: string; offline?: boolean; bot?: boolean }) {
  return <div className={`flex items-center gap-2 text-sm ${offline ? "opacity-40" : "text-[var(--discord-text-muted)]"}`}><Avatar initials={initials} color={color} /><span className="truncate">{name}</span>{bot && <span className="rounded bg-[var(--discord-brand)] px-1 text-[9px] text-white">BOT</span>}</div>;
}
