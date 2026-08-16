/**
 * fundDisplayName (Phase E-3, founder 2026-08-16) — DISPLAY-ONLY short-name
 * shaping for discovery surfaces (leaderboard, explorer). Splits plan/variant
 * qualifiers into a small tag, abbreviates structural terms, and applies a
 * small fixed AMC brand map. The stored fund_name_short (and the SCHEME_KEY
 * counting/dedup rule built on it) is NEVER touched — this runs at render
 * time only, and callers keep the full original name in a hover title.
 * Transactional/identity surfaces (portfolio, fund-detail header) deliberately
 * keep the full official name.
 */

/** Universal structural abbreviations — cannot change a fund's identity. */
const STRUCT_ABBREV: [RegExp, string][] = [
  [/\bExchange Traded Fund\b/gi, 'ETF'],
  [/\bFund of Funds?\b/gi, 'FoF'],
];

/** Small FIXED brand map (standard Indian-MF-app convention) — never automatic
 *  word-chopping; extend only with well-known short forms. */
const AMC_ABBREV: [RegExp, string][] = [
  [/^ICICI Prudential\b/i, 'ICICI Pru'],
  [/^Aditya Birla Sun Life\b/i, 'ABSL'],
  [/^Franklin Templeton\b/i, 'Franklin'],
  [/^Motilal Oswal\b/i, 'Motilal'],
  [/^Kotak Mahindra\b/i, 'Kotak'],
];

/** A " - " segment is a QUALIFIER (goes to the tag) when it names a plan /
 *  option / variant — finite vocabulary, so the split is deterministic. A
 *  segment like "April 2030" (Bharat Bond) matches nothing and stays in the
 *  core name. */
const QUALIFIER_RE =
  /\b(direct|regular)\b|\bplan\b|\bgrowth\b|\bidcw\b|\bdividend\b|\bunclaimed\b|\btransitory\b|\bsegregated\b|\boption\b|\breinvest|\bpayout\b|\bbonus\b/i;

/** Parenthetical side-pocket count mentions ("(no. of segregated portfolios- 3)")
 *  are disclosures, not identity — moved to the tag. */
const PAREN_QUALIFIER_RE = /\s*\(([^)]*(?:segregated|portfolio)[^)]*)\)/i;

export function fundDisplayName(raw: string): { name: string; tag?: string } {
  let s = raw.trim();
  const tags: string[] = [];

  const paren = s.match(PAREN_QUALIFIER_RE);
  if (paren) {
    tags.push(paren[1].trim());
    s = s.replace(PAREN_QUALIFIER_RE, '').trim();
  }

  for (const [re, to] of STRUCT_ABBREV) s = s.replace(re, to);
  for (const [re, to] of AMC_ABBREV) {
    if (re.test(s)) {
      s = s.replace(re, to);
      break;
    }
  }

  const parts = s.split(/\s+[-–]\s+/);
  if (parts.length > 1) {
    // First segment is always the name; later segments split by vocabulary.
    const core: string[] = [parts[0]];
    for (const p of parts.slice(1)) (QUALIFIER_RE.test(p) ? tags : core).push(p);
    s = core.join(' - ');
  }

  const name = s.trim();
  if (!name) return { name: raw.trim() }; // degenerate: everything was qualifier
  return tags.length ? { name, tag: tags.join(' · ') } : { name };
}
