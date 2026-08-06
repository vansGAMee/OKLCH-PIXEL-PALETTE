/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
/**
 * src/components/dashboard/InsightsTab.tsx
 * User workflow funnel from palette_events.
 * Loaded dynamically on the Insights tab only.
 */
import React, { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { WorkflowFunnel } from '@/components/insights/WorkflowFunnel';
import { BarChart2, Loader2 } from 'lucide-react';

interface StageData {
  stage: string;
  label: string;
  count: number;
}

const EVENT_STAGES = [
  { event: 'palette_generated', label: 'Generated' },
  { event: 'palette_saved', label: 'Saved' },
  { event: 'palette_published', label: 'Published' },
  { event: 'palette_remixed', label: 'Remixed' },
  { event: 'palette_exported', label: 'Exported' },
] as const;

const EVENT_STAGES_RU = [
  { event: 'palette_generated', label: 'Создано' },
  { event: 'palette_saved', label: 'Сохранено' },
  { event: 'palette_published', label: 'Опубликовано' },
  { event: 'palette_remixed', label: 'Ремикс' },
  { event: 'palette_exported', label: 'Экспорт' },
] as const;

export function InsightsTab({ locale }: { locale: 'en' | 'ru' }) {
  const [stages, setStages] = useState<StageData[]>([]);
  const [loading, setLoading] = useState(true);
  const isRu = locale === 'ru';

  useEffect(() => {
    let isMounted = true;
    const supabase = createClient();
    if (!supabase) {
      Promise.resolve().then(() => { if (isMounted) setLoading(false); });
      return;
    }

    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user || !isMounted) { if (isMounted) setLoading(false); return; }

      // Query counts for each event type in one request
      const { data } = await (supabase as any)
        .from('palette_events')
        .select('event_name')
        .eq('user_id', user.id);

      if (data && isMounted) {
        const counts: Record<string, number> = {};
        (data as any[]).forEach((row) => {
          counts[row.event_name] = (counts[row.event_name] ?? 0) + 1;
        });

        const eventLabels = isRu ? EVENT_STAGES_RU : EVENT_STAGES;
        setStages(
          eventLabels.map((s) => ({
            stage: s.event,
            label: s.label,
            count: counts[s.event] ?? 0,
          }))
        );
      }
      if (isMounted) setLoading(false);
    });

    return () => { isMounted = false; };
  }, [isRu]);

  const totalEvents = stages.reduce((sum, s) => sum + s.count, 0);

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-2">
        <BarChart2 className="w-5 h-5 text-purple-400" />
        <h2 className="text-sm font-mono font-bold text-white">
          {isRu ? 'Мой воркфлоу' : 'My Workflow'}
        </h2>
      </div>

      <div className="glass-panel rounded-xl border border-white/10 p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
          </div>
        ) : totalEvents === 0 ? (
          <div className="text-center py-12 space-y-3">
            <div className="text-3xl">📊</div>
            <p className="text-sm font-mono text-gray-400">
              {isRu
                ? 'Данных пока нет. Создайте палитру в редакторе!'
                : 'Use the studio to build your first workflow.'}
            </p>
          </div>
        ) : (
          <WorkflowFunnel stages={stages} locale={locale} />
        )}
      </div>

      <p className="text-xs font-mono text-gray-500">
        {isRu
          ? 'Только ваши данные. Никакой глобальной статистики.'
          : 'Your data only. No global tracking.'}
      </p>
    </div>
  );
}
