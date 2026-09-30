import * as React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { SiteFooter } from './SiteFooter';

describe('SiteFooter', () => {
  it('links to /data-deletion under Account', () => {
    render(<SiteFooter />);
    const link = screen.getByRole('link', { name: 'Data deletion' });
    expect(link.getAttribute('href')).toBe('/data-deletion');
  });
});
