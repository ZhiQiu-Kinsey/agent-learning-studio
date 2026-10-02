/* eslint-disable react/no-unknown-property */
// Adapted from https://reactbits.dev/r/Lanyard-TS-TW.json (MIT + Commons Clause).
// Card model and band texture: src/assets/lanyard/card.glb and lanyard.png from
// the React Bits repository (same licence). Changes: sized to its parent
// instead of the viewport, the render/physics loop follows `active` (off
// screen or hidden tab -> frameloop "never"), desktop-only so no mobile branch,
// the front face takes a caller-drawn image (atlas upscaled to keep its
// resolution), and dpr / anchor height are props. Import it with React.lazy:
// three / fiber / drei / rapier only load where the badge is shown.
import { Canvas } from "@react-three/fiber";
import { Environment, Lightformer } from "@react-three/drei";
import { Physics } from "@react-three/rapier";
import * as THREE from "three";
import { Band } from "./Lanyard/Band";

export default function Lanyard({
  frontImage,
  active,
  position = [0, 0, 13],
  gravity = [0, -40, 0],
  fov = 20,
  dpr = [1, 2],
  anchorY = 4,
  className = "",
}: {
  frontImage: string;
  active: boolean;
  position?: [number, number, number];
  gravity?: [number, number, number];
  fov?: number;
  /** Render resolution range (device pixel ratio), as in R3F's Canvas. */
  dpr?: [number, number];
  /** Height of the band's fixed anchor; raise it to hang the card higher. */
  anchorY?: number;
  className?: string;
}) {
  return (
    <div className={`rb-lanyard ${className}`}>
      <Canvas
        camera={{ position, fov }}
        dpr={dpr}
        frameloop={active ? "always" : "never"}
        gl={{ alpha: true }}
        onCreated={({ gl }) => gl.setClearColor(new THREE.Color(0x000000), 0)}
      >
        <ambientLight intensity={Math.PI} />
        <Physics gravity={gravity} timeStep={1 / 60} paused={!active}>
          <Band frontImage={frontImage} anchorY={anchorY} />
        </Physics>
        <Environment blur={0.75}>
          <Lightformer
            intensity={2}
            color="white"
            position={[0, -1, 5]}
            rotation={[0, 0, Math.PI / 3]}
            scale={[100, 0.1, 1]}
          />
          <Lightformer
            intensity={3}
            color="white"
            position={[-1, -1, 1]}
            rotation={[0, 0, Math.PI / 3]}
            scale={[100, 0.1, 1]}
          />
          <Lightformer
            intensity={3}
            color="white"
            position={[1, 1, 1]}
            rotation={[0, 0, Math.PI / 3]}
            scale={[100, 0.1, 1]}
          />
          <Lightformer
            intensity={10}
            color="white"
            position={[-10, 0, 14]}
            rotation={[0, Math.PI / 2, Math.PI / 3]}
            scale={[100, 10, 1]}
          />
        </Environment>
      </Canvas>
    </div>
  );
}
