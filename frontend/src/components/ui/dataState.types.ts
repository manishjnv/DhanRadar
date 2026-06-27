/**
 * Status/reason types for the DataState render-gate.
 *
 * Single source of truth is the data envelope (src/data/envelope.ts, §5); this file just
 * re-exports so existing `./dataState.types` imports keep working without a second definition.
 */
export type { DataStatus, DataReason } from '@/data/envelope';
