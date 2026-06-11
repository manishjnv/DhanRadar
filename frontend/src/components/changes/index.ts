/**
 * changes — barrel export
 *
 * Consumer mounting point: import { WhatChangedPanel } from '@/components/changes'
 * and render <WhatChangedPanel data={changesData} /> on the portfolio detail page
 * (or any surface that has fetched usePortfolioChanges).
 */
export { WhatChangedPanel } from './WhatChangedPanel';
export type {
  PortfolioChangesData,
  FundChange,
  ChangeKind,
  WhatChangedPanelProps,
} from './WhatChangedPanel';
