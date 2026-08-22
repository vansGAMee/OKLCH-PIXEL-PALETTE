import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

interface ToolCardProps {
  title: string;
  description: string;
  href: string;
  badge?: string;
  available?: boolean;
}

export function ToolCard({ title, description, href, badge, available = true }: ToolCardProps) {
  if (!available) {
    return (
      <div className="glass-panel rounded-xl border border-white/10 p-5 opacity-50 cursor-not-allowed">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="text-sm font-mono font-bold text-white">{title}</h3>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-zinc-700/60 text-gray-400 whitespace-nowrap shrink-0">
            Soon
          </span>
        </div>
        <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="glass-panel rounded-xl border border-white/10 hover:border-purple-500/40 p-5 group transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 block"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-sm font-mono font-bold text-white group-hover:text-purple-300 transition-colors">
          {title}
        </h3>
        <div className="flex items-center gap-1.5 shrink-0">
          {badge && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300">
              {badge}
            </span>
          )}
          <ArrowRight className="w-3.5 h-3.5 text-gray-500 group-hover:text-purple-400 group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
    </Link>
  );
}
