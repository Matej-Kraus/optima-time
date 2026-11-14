import { useRef, type PointerEvent, type ReactNode } from "react";
import { clamp01, type Point } from "../api";

interface Props {
  src: string | null;
  emptyText: string;
  children?: ReactNode;
  onPointerDown?: (p: Point, e: PointerEvent<SVGSVGElement>) => void;
  onPointerMove?: (p: Point, e: PointerEvent<SVGSVGElement>) => void;
  onPointerUp?: (p: Point, e: PointerEvent<SVGSVGElement>) => void;
  crosshair?: boolean;
  onImageError?: () => void;
}

/** An image with an SVG overlay in relative coordinates (0-1 on both axes). */
export function Overlay({ src, emptyText, children, onPointerDown, onPointerMove, onPointerUp, crosshair, onImageError }: Props) {
  const svg = useRef<SVGSVGElement>(null);

  const rel = (e: PointerEvent<SVGSVGElement>): Point => {
    const box = svg.current!.getBoundingClientRect();
    return [clamp01((e.clientX - box.left) / box.width), clamp01((e.clientY - box.top) / box.height)];
  };

  return (
    <div className="overlay">
      {src ? <img src={src} alt="" draggable={false} onError={onImageError} /> : <div className="empty">{emptyText}</div>}
      {src && (
        <svg
          ref={svg}
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className={crosshair ? "crosshair" : undefined}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            onPointerDown?.(rel(e), e);
          }}
          onPointerMove={(e) => onPointerMove?.(rel(e), e)}
          onPointerUp={(e) => onPointerUp?.(rel(e), e)}
        >
          {children}
        </svg>
      )}
    </div>
  );
}
