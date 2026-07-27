/** Pixel-style button (system font + chunky bottom border). */

import type { ButtonHTMLAttributes } from 'react';

export function PixelButton({
  variant = 'default',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' }): JSX.Element {
  const cls = ['pixel-btn', variant === 'primary' ? 'pixel-btn--primary' : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return <button type="button" className={cls} {...props} />;
}
