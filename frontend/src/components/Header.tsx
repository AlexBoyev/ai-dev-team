import { Loader } from "lucide-react";

interface Props {
  running: boolean;
}

export default function Header({ running }: Props) {
  return (
    <header className="header">
      <div className="header-left">
        <span className="header-logo">⚡ AI Dev Team</span>
        <span className="header-sub">Autonomous code analysis pipeline</span>
      </div>
      <div className="header-right">
        {running && (
          <span style={{ display: "flex", alignItems: "center", gap: 6,
                         fontSize: 12, color: "#3b82f6" }}>
            <Loader size={13} className="spinning" />
            Pipeline running…
          </span>
        )}
      </div>
    </header>
  );
}
