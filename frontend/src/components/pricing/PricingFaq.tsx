'use client';

/**
 * PricingFaq — Reusable accordion for FAQ items.
 *
 * Compliance checklist:
 *  #1  No advisory copy — no buy/sell/switch verbs except inside negation sentences.
 *  #9  No numeric score, fair value, or price target mentioned.
 *
 * Accessibility:
 *  - Native <button> triggers: Enter/Space work for free.
 *  - aria-expanded / aria-controls wired on each trigger.
 *  - role="region" + aria-labelledby on each panel.
 *  - ChevronDown icon is aria-hidden.
 *  - Focus ring via shared token class.
 *
 * Animation: grid-template-rows 0fr → 1fr technique (no JS height calc).
 */

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface FaqItem {
  q: string;
  a: string;
}

// ---------------------------------------------------------------------------
// Default FAQ content for the pricing page (non-advisory)
// ---------------------------------------------------------------------------
const DEFAULT_ITEMS: FaqItem[] = [
  {
    q: 'Is DhanRadar investment advice?',
    a: 'No. DhanRadar is an educational research-analytics product. We describe each fund\'s category-relative form and explain tax rules — we never tell you to buy, sell, or switch. Investments are subject to market risk.',
  },
  {
    q: 'What is included in the Free plan?',
    a: 'The Free plan lets you upload your CAS and get every fund labelled with a plain-English, category-relative label (In Form / On Track / Off Track), a confidence band (high / medium / low), basic explainers for each label, Market Mood, Tax Education, and one portfolio. There is no numeric score — ever.',
  },
  {
    q: 'When does Founding Access end?',
    a: 'Founding Access is free until we launch publicly, plus a grace window after. We will give every founding member clear advance notice before anything changes.',
  },
  {
    q: 'Will I be charged now?',
    a: 'No. Paid checkout is not live yet — you cannot be charged today. Founding Access simply reserves your spot and locks in founding-member status.',
  },
  {
    q: 'Do you show a score or a target price?',
    a: 'No. By design there is no numeric score, fair value, or price target anywhere on DhanRadar — only an educational label and a confidence band.',
  },
];

// ---------------------------------------------------------------------------
// Shared focus-ring class (matches the landing-page pattern)
// ---------------------------------------------------------------------------
const LINK_RING =
  'rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40';

// ---------------------------------------------------------------------------
// Accordion item
// ---------------------------------------------------------------------------
function AccordionItem({
  item,
  index,
  isOpen,
  onToggle,
}: {
  item: FaqItem;
  index: number;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const triggerId = `faq-trigger-${index}`;
  const panelId = `faq-panel-${index}`;

  return (
    <div className="border-b border-line last:border-b-0">
      <button
        id={triggerId}
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={onToggle}
        className={`
          flex w-full items-center justify-between gap-4
          py-4 text-left text-body font-medium text-ink
          transition-colors hover:text-royal
          ${LINK_RING}
        `}
      >
        <span>{item.q}</span>
        <ChevronDown
          aria-hidden="true"
          size={16}
          strokeWidth={1.75}
          className={`
            shrink-0 text-ink-muted transition-transform duration-200
            ${isOpen ? 'rotate-180' : 'rotate-0'}
          `}
        />
      </button>

      {/* grid-rows trick: 0fr → 1fr avoids JS height measurement */}
      <div
        id={panelId}
        role="region"
        aria-labelledby={triggerId}
        className={`
          grid transition-all duration-200 ease-in-out
          ${isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}
        `}
      >
        <div className="overflow-hidden">
          <p className="pb-4 text-body text-ink-secondary">{item.a}</p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PricingFaq — public export (single-open accordion)
// ---------------------------------------------------------------------------
export function PricingFaq({ items = DEFAULT_ITEMS }: { items?: FaqItem[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  function toggle(idx: number) {
    setOpenIndex((prev) => (prev === idx ? null : idx));
  }

  return (
    <div>
      {items.map((item, idx) => (
        <AccordionItem
          key={item.q}
          item={item}
          index={idx}
          isOpen={openIndex === idx}
          onToggle={() => toggle(idx)}
        />
      ))}
    </div>
  );
}

export default PricingFaq;
