'use client';
/**
 * src/components/quality/QualityInspector.tsx
 * Palette quality warnings panel for the Studio.
 */
import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, AlertTriangle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import type { QualityReport, QualityWarning } from '@/lib/color/qualityInspector';

interface QualityInspectorProps {
  report: QualityReport;
  locale?: 'en' | 'ru';
}

function WarningIcon({ severity }: { severity: QualityWarning['severity'] }) {
  switch (severity) {
    case 'error': return <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />;
    case 'warning': return <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />;
    case 'info': return <Info className="w-4 h-4 text-blue-400 flex-shrink-0" />;
  }
}

export function QualityInspector({ report, locale = 'en' }: QualityInspectorProps) {
  const [open, setOpen] = useState(true);
  const isRu = locale === 'ru';

  const statusColor = report.hasErrors
    ? 'text-red-400 border-red-500/20 bg-red-500/10'
    : report.hasWarnings
      ? 'text-amber-400 border-amber-500/20 bg-amber-500/10'
      : 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10';

  const statusText = report.hasErrors
    ? (isRu ? 'Ошибки найдены' : 'Issues found')
    : report.hasWarnings
      ? (isRu ? 'Рекомендации' : 'Recommendations')
      : (isRu ? 'Всё в порядке' : 'Looking good');

  return (
    <div className="glass-panel rounded-xl border border-white/10 overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-purple-400" />
          <span className="text-xs font-mono font-bold text-gray-200 uppercase tracking-widest">
            {isRu ? 'Анализ палитры' : 'Palette Inspector'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${statusColor}`}>
            {statusText}
          </span>
          {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-white/5 p-4 space-y-2">
          {report.warnings.length === 0 ? (
            <p className="text-xs font-mono text-emerald-400">
              {isRu ? 'Проблем не найдено.' : 'No issues detected.'}
            </p>
          ) : (
            report.warnings.map((w) => (
              <div
                key={w.id}
                className="flex items-start gap-2 text-xs font-sans text-gray-300 leading-relaxed"
              >
                <WarningIcon severity={w.severity} />
                <span>{isRu ? w.messageRu : w.messageEn}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
