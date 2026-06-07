import { render, screen, fireEvent } from '@testing-library/react';
import { Input, Field } from './Input';

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
});
