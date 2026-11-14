import type { Point } from "../api";
import { magnifierOffset } from "../magnifier";

interface Props {
  src: string;
  at: Point; // relative position in the image
  hostWidth: number; // displayed image size in px
  hostHeight: number;
  zoom?: number;
  size?: number;
}

/** A round magnifier showing the image around `at`, for placing corners precisely (SPEC 13.1). */
export function Magnifier({ src, at, hostWidth, hostHeight, zoom = 4, size = 160 }: Props) {
  if (!hostWidth || !hostHeight) return null;
  const [bx, by] = magnifierOffset(at, hostWidth, hostHeight, zoom, size);
  return (
    <div
      className="magnifier"
      style={{
        width: size,
        height: size,
        left: at[0] * hostWidth - size / 2,
        top: Math.max(0, at[1] * hostHeight - size - 24),
        backgroundImage: `url(${src})`,
        backgroundSize: `${hostWidth * zoom}px ${hostHeight * zoom}px`,
        backgroundPosition: `${bx}px ${by}px`,
      }}
    >
      <div className="crosshair-mark" />
    </div>
  );
}
