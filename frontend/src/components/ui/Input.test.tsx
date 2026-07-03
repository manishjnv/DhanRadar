import { render, screen, fireEvent } from '@testing-library/react';
import { Input, Field, PasswordInput } from './Input';

describe('Input', () => {
  it('renders an input element', () => {
    render(<Input data-testid="inp" />);
    expect(screen.getByTestId('inp')).toBeInTheDocument();
  });

  it('forwards placeholder prop', () => {
    render(<Input placeholder="Enter PAN" />);
    expect(screen.getByPlaceholderText('Enter PAN')).toBeInTheDocument();
  });

  it('reflects typed value via fireEvent', () => {
    render(<Input data-testid="inp" defaultValue="" />);
    const inp = screen.getByTestId('inp') as HTMLInputElement;
    fireEvent.change(inp, { target: { value: 'ABCDE1234F' } });
    expect(inp.value).toBe('ABCDE1234F');
  });

  it('is disabled when disabled prop is set', () => {
    render(<Input data-testid="inp" disabled />);
    expect(screen.getByTestId('inp')).toBeDisabled();
  });
});

describe('PasswordInput', () => {
  it('starts masked (type=password)', () => {
    render(<PasswordInput data-testid="pwd" />);
    expect(screen.getByTestId('pwd')).toHaveAttribute('type', 'password');
  });

  it('toggling the eye button flips the input to type=text and back', () => {
    render(<PasswordInput data-testid="pwd" />);
    const input = screen.getByTestId('pwd');
    const toggle = screen.getByRole('button', { name: /show password/i });

    fireEvent.click(toggle);
    expect(input).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: /hide password/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /hide password/i }));
    expect(input).toHaveAttribute('type', 'password');
  });

  it('forwards value/onChange like a normal Input', () => {
    render(<PasswordInput data-testid="pwd" defaultValue="" />);
    const input = screen.getByTestId('pwd') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'ABCDE1234F' } });
    expect(input.value).toBe('ABCDE1234F');
  });
});

describe('Field', () => {
  it('renders label text', () => {
    render(
      <Field id="pan" label="PAN Number">
        <Input id="pan" />
      </Field>,
    );
    expect(screen.getByText('PAN Number')).toBeInTheDocument();
  });

  it('wires label htmlFor to input id', () => {
    render(
      <Field id="pan" label="PAN Number">
        <Input id="pan" />
      </Field>,
    );
    const label = screen.getByText('PAN Number') as HTMLLabelElement;
    expect(label.htmlFor).toBe('pan');
  });

  it('renders error message with role=alert', () => {
    render(
      <Field id="pan" label="PAN Number" error="Invalid PAN">
        <Input id="pan" />
      </Field>,
    );
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Invalid PAN');
  });

  it('renders hint when no error', () => {
    render(
      <Field id="pan" label="PAN Number" hint="10-character PAN">
        <Input id="pan" />
      </Field>,
    );
    expect(screen.getByText('10-character PAN')).toBeInTheDocument();
  });

  it('wires aria-describedby to error element and aria-invalid when error is set', () => {
    render(
      <Field id="pan" label="PAN Number" error="Invalid PAN">
        <Input />
      </Field>,
    );
    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('aria-describedby', 'pan-error');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    // The referenced element must exist in the DOM
    expect(document.getElementById('pan-error')).toBeInTheDocument();
  });

  it('wires aria-describedby to hint element when only hint is set', () => {
    render(
      <Field id="email" label="Email" hint="We will never share your email">
        <Input />
      </Field>,
    );
    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('aria-describedby', 'email-hint');
    expect(input).not.toHaveAttribute('aria-invalid');
    expect(document.getElementById('email-hint')).toBeInTheDocument();
  });

  it('does not set aria-describedby when neither hint nor error is present', () => {
    render(
      <Field id="name" label="Name">
        <Input />
      </Field>,
    );
    const input = screen.getByRole('textbox');
    expect(input).not.toHaveAttribute('aria-describedby');
    expect(input).not.toHaveAttribute('aria-invalid');
  });

  it('respects caller-provided aria-describedby by merging it', () => {
    render(
      <Field id="amount" label="Amount" hint="In INR">
        <Input aria-describedby="amount-extra" />
      </Field>,
    );
    const input = screen.getByRole('textbox');
    // Both the caller's value and the Field's hint id should appear
    expect(input.getAttribute('aria-describedby')).toContain('amount-extra');
    expect(input.getAttribute('aria-describedby')).toContain('amount-hint');
  });

  it('injects id onto child when caller does not provide one', () => {
    render(
      <Field id="mobile" label="Mobile">
        <Input />
      </Field>,
    );
    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('id', 'mobile');
  });
});
