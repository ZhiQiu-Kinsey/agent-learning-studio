// React Bits DecryptedText, adapted from https://reactbits.dev/r/DecryptedText-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. Stable screen-reader text; finite view reveal.
import { useEffect, useState } from "react";
import { useMotionBudget } from "../../motion";

export default function DecryptedText({
  text,
  className = "",
  speed = 35,
  characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
}: {
  text: string;
  className?: string;
  speed?: number;
  characters?: string;
}) {
  const { ref, active, reduced } = useMotionBudget<HTMLSpanElement>();
  const [display, setDisplay] = useState(text);
  const [completed, setCompleted] = useState(false);
  useEffect(() => {
    if (!active || completed) return;
    let revealed = 0;
    const timer = setInterval(() => {
      revealed += 2;
      setDisplay(
        Array.from(text)
          .map((char, index) =>
            index < revealed || char === " "
              ? char
              : characters[Math.floor(Math.random() * characters.length)],
          )
          .join(""),
      );
      if (revealed >= text.length) {
        clearInterval(timer);
        setCompleted(true);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [active, characters, completed, speed, text]);
  return (
    <span
      ref={ref}
      className={`rb-decrypted-text ${className}`}
      aria-label={text}
    >
      <span aria-hidden="true">{reduced || !active ? text : display}</span>
    </span>
  );
}
