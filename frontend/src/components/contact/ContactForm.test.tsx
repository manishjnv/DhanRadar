/**
 * ContactForm — client validation, honeypot, submit success/429/503, and
 * email prefill from useMe().
 */
import * as React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/lib/apiClient', async () => {
  const actual = await vi.importActual<typeof import('@/lib/apiClient')>('@/lib/apiClient');
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

import { api, ApiError } from '@/lib/apiClient';
import { ContactForm } from './ContactForm';

const mockGet = api.get as unknown as ReturnType<typeof vi.fn>;
const mockPost = api.post as unknown as ReturnType<typeof vi.fn>;

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ContactForm />
    </QueryClientProvider>,
  );
}

const VALID = {
  name: 'Asha Rao',
  email: 'asha@example.com',
  message: 'Hello, I have a question about my portfolio report.',
};

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Name'), VALID.name);
  await user.clear(screen.getByLabelText('Email'));
  await user.type(screen.getByLabelText('Email'), VALID.email);
  await user.type(screen.getByLabelText('Message'), VALID.message);
}

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  // Anonymous by default — /auth/me 401s.
  mockGet.mockRejectedValue(
    new ApiError({ type: 'about:blank', title: 'Unauthorized', status: 401, request_id: 'r1' }),
  );
});

describe('ContactForm', () => {
  it('renders the fields and a visually-hidden honeypot', () => {
    renderForm();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Topic')).toBeInTheDocument();
    expect(screen.getByLabelText('Message')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeInTheDocument();

    const honeypot = screen.getByLabelText('Website', { selector: 'input' });
    expect(honeypot).toHaveAttribute('aria-hidden', 'true');
    expect(honeypot).toHaveAttribute('tabindex', '-1');
    expect(honeypot).toHaveAttribute('autocomplete', 'off');
  });

  it('shows the topic options with plain-language labels', () => {
    renderForm();
    const select = screen.getByLabelText('Topic') as HTMLSelectElement;
    const labels = Array.from(select.options).map((o) => o.textContent);
    expect(labels).toEqual([
      'General question',
      'My account',
      'Delete my data',
      'Feedback',
      'Partnership',
      'Other',
    ]);
  });

  it('shows a live character counter for the message field', async () => {
    const user = userEvent.setup();
    renderForm();
    expect(screen.getByText('0 / 3000')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Message'), 'hello');
    expect(screen.getByText('5 / 3000')).toBeInTheDocument();
  });

  it('blocks submit and shows inline errors on invalid input', async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Enter your name.')).toBeInTheDocument();
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByText(/Message must be at least/)).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();

    const nameInput = screen.getByLabelText('Name');
    expect(nameInput).toHaveAttribute('aria-describedby', 'contact-name-error');
  });

  it('submits the right body on valid input and shows success', async () => {
    mockPost.mockResolvedValue({ status: 'received' });
    const user = userEvent.setup();
    renderForm();
    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost).toHaveBeenCalledWith('/contact', {
      name: VALID.name,
      email: VALID.email,
      topic: 'general',
      message: VALID.message,
      website: '',
    });

    const status = await screen.findByRole('status');
    expect(status.textContent).toContain(`will reply to ${VALID.email}`);

    // "Send another message" resets the form.
    await user.click(screen.getByRole('button', { name: 'Send another message' }));
    expect(screen.getByLabelText('Name')).toHaveValue('');
  });

  it('shows the rate-limit message on 429', async () => {
    mockPost.mockRejectedValue(
      new ApiError({ type: 'about:blank', title: 'Too Many Requests', status: 429, request_id: 'r2' }),
    );
    const user = userEvent.setup();
    renderForm();
    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('sent a few messages already');
    expect(alert.textContent).toContain('connect@dhanradar.com');
  });

  it('shows the fallback message on 503 / network error', async () => {
    mockPost.mockRejectedValue(
      new ApiError({ type: 'about:blank', title: 'Service Unavailable', status: 503, request_id: 'r3' }),
    );
    const user = userEvent.setup();
    renderForm();
    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain("couldn't send your message");
    expect(alert.textContent).toContain('connect@dhanradar.com');
  });

  it('prefills email from useMe() when signed in, still editable', async () => {
    mockGet.mockResolvedValue({ user: { id: 'u1', email: 'signedin@example.com' } });
    renderForm();

    await waitFor(() =>
      expect(screen.getByLabelText('Email')).toHaveValue('signedin@example.com'),
    );

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'changed@example.com');
    expect(screen.getByLabelText('Email')).toHaveValue('changed@example.com');
  });
});
