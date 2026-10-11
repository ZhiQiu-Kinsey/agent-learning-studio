// Adapted from https://reactbits.dev/r/CountUp-TS-TW.json (MIT + Commons Clause).
// The upstream spring has a long tail (numbers sit a few short of the real value
// for seconds); this version tweens with an ease-out and always lands exactly on
// `to`. Static motion shows the final value at once.
'use client';

import { animate, useInView } from 'motion/react';
import { useCallback, useEffect, useRef } from 'react';
import { useReducedMotion } from '../../motion';

interface CountUpProps {
  to: number;
  from?: number;
  direction?: 'up' | 'down';
  delay?: number;
  duration?: number;
  className?: string;
  startWhen?: boolean;
  separator?: string;
  onStart?: () => void;
  onEnd?: () => void;
}

export default function CountUp({
  to,
  from = 0,
  direction = 'up',
  delay = 0,
  duration = 2,
  className = '',
  startWhen = true,
  separator = '',
  onStart,
  onEnd
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const isInView = useInView(ref, { once: true, margin: '0px' });
  const start = direction === 'down' ? to : from;
  const target = direction === 'down' ? from : to;
  // Last value written, so a changed target continues from where it is.
  const shown = useRef<number | null>(null);

  const decimals = (num: number) => {
    const [, fraction = ''] = num.toString().split('.');
    return parseInt(fraction || '0') !== 0 ? fraction.length : 0;
  };
  const maxDecimals = Math.max(decimals(from), decimals(to));

  const formatValue = useCallback(
    (latest: number) => {
      // Local change: format in the page language (<html lang>), not a fixed 'en-US'.
      const formatted = Intl.NumberFormat(document.documentElement.lang || undefined, {
        useGrouping: !!separator,
        minimumFractionDigits: maxDecimals,
        maximumFractionDigits: maxDecimals
      }).format(latest);
      return separator ? formatted.replace(/,/g, separator) : formatted;
    },
    [maxDecimals, separator]
  );

  const write = useCallback(
    (value: number) => {
      shown.current = value;
      if (ref.current) ref.current.textContent = formatValue(value);
    },
    [formatValue]
  );

  useEffect(() => {
    if (shown.current === null) write(reduced ? target : start);
  }, [reduced, start, target, write]);

  useEffect(() => {
    if (!isInView || !startWhen) return;
    if (reduced) {
      write(target);
      return;
    }
    onStart?.();
    const controls = animate(shown.current ?? start, target, {
      duration,
      delay,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: write,
      onComplete: () => {
        write(target);
        onEnd?.();
      }
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInView, startWhen, reduced, target, duration, delay]);

  return <span className={className} ref={ref} />;
}
