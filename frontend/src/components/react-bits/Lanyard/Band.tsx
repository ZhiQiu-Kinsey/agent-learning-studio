// Adapted from https://reactbits.dev/r/Lanyard-TS-TW.json (MIT + Commons Clause).
/* eslint-disable react/no-unknown-property */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  extend,
  useFrame,
  useThree,
  type ThreeElement,
  type ThreeEvent,
} from "@react-three/fiber";
import { useGLTF, useTexture } from "@react-three/drei";
import {
  BallCollider,
  CuboidCollider,
  RigidBody,
  useRopeJoint,
  useSphericalJoint,
  type RapierRigidBody,
  type RigidBodyProps,
} from "@react-three/rapier";
import { MeshLineGeometry, MeshLineMaterial } from "meshline";
import * as THREE from "three";
import cardGLB from "../../../assets/lanyard/card.glb";
import lanyardTexture from "../../../assets/lanyard/lanyard.png";

extend({ MeshLineGeometry, MeshLineMaterial });

declare module "@react-three/fiber" {
  interface ThreeElements {
    meshLineGeometry: ThreeElement<typeof MeshLineGeometry>;
    meshLineMaterial: ThreeElement<typeof MeshLineMaterial>;
  }
}

// Front face of the card model = left half of its texture atlas.
const FRONT_UV_RECT = { x: 0, y: 0, w: 0.5, h: 0.755 };

type LanyardRigidBody = RapierRigidBody & { lerped?: THREE.Vector3 };

export function Band({
  frontImage,
  anchorY,
  maxSpeed = 50,
  minSpeed = 0,
}: {
  frontImage: string;
  anchorY: number;
  maxSpeed?: number;
  minSpeed?: number;
}) {
  const band = useRef<
    THREE.Mesh<
      InstanceType<typeof MeshLineGeometry>,
      InstanceType<typeof MeshLineMaterial>
    >
  >(null!);
  const fixed = useRef<RapierRigidBody>(null!);
  const j1 = useRef<LanyardRigidBody>(null!);
  const j2 = useRef<LanyardRigidBody>(null!);
  const j3 = useRef<RapierRigidBody>(null!);
  const card = useRef<RapierRigidBody>(null!);
  const [vec] = useState(() => new THREE.Vector3());
  const [ang] = useState(() => new THREE.Vector3());
  const [rot] = useState(() => new THREE.Vector3());
  const [dir] = useState(() => new THREE.Vector3());
  const segmentProps: RigidBodyProps = {
    type: "dynamic",
    canSleep: true,
    colliders: false,
    angularDamping: 4,
    linearDamping: 4,
  };
  const lerpedOf = (body: LanyardRigidBody) =>
    (body.lerped ??= new THREE.Vector3().copy(body.translation()));

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { nodes, materials } = useGLTF(cardGLB) as any;
  const texture = useTexture(lanyardTexture);
  const frontTex = useTexture(frontImage);

  const maxTexture = useThree((state) => state.gl.capabilities.maxTextureSize);

  // Composite the drawn face into the card atlas (aspect-preserving cover).
  // The atlas is upscaled so the face keeps its own resolution instead of
  // being squeezed into the model's original texture size.
  const cardMap = useMemo(() => {
    const baseMap = materials.base.map as THREE.Texture;
    const baseImg = baseMap.image as HTMLImageElement;
    const img = frontTex.image as HTMLImageElement | undefined;
    const upscale = img
      ? Math.min(
          Math.max(1, img.width / (FRONT_UV_RECT.w * baseImg.width)),
          maxTexture / Math.max(baseImg.width, baseImg.height),
          4,
        )
      : 1;
    const W = Math.round(baseImg.width * upscale);
    const H = Math.round(baseImg.height * upscale);
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx || !img) return baseMap;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(baseImg, 0, 0, W, H);
    const rx = FRONT_UV_RECT.x * W;
    const ry = FRONT_UV_RECT.y * H;
    const rw = FRONT_UV_RECT.w * W;
    const rh = FRONT_UV_RECT.h * H;
    const scale = Math.max(rw / img.width, rh / img.height);
    const dw = img.width * scale;
    const dh = img.height * scale;
    ctx.save();
    ctx.beginPath();
    ctx.rect(rx, ry, rw, rh);
    ctx.clip();
    ctx.drawImage(img, rx + (rw - dw) / 2, ry + (rh - dh) / 2, dw, dh);
    ctx.restore();
    const composite = new THREE.CanvasTexture(canvas);
    composite.colorSpace = THREE.SRGBColorSpace;
    composite.flipY = baseMap.flipY;
    composite.anisotropy = 16;
    composite.needsUpdate = true;
    return composite;
  }, [frontTex, materials.base.map, maxTexture]);
  useEffect(() => () => cardMap.dispose(), [cardMap]);

  const [curve] = useState(
    () =>
      new THREE.CatmullRomCurve3([
        new THREE.Vector3(),
        new THREE.Vector3(),
        new THREE.Vector3(),
        new THREE.Vector3(),
      ]),
  );
  const [dragged, drag] = useState<false | THREE.Vector3>(false);
  const [hovered, hover] = useState(false);

  useRopeJoint(fixed, j1, [[0, 0, 0], [0, 0, 0], 1]);
  useRopeJoint(j1, j2, [[0, 0, 0], [0, 0, 0], 1]);
  useRopeJoint(j2, j3, [[0, 0, 0], [0, 0, 0], 1]);
  useSphericalJoint(j3, card, [
    [0, 0, 0],
    [0, 1.45, 0],
  ]);

  useEffect(() => {
    if (!hovered) return;
    document.body.style.cursor = dragged ? "grabbing" : "grab";
    return () => {
      document.body.style.cursor = "";
    };
  }, [hovered, dragged]);

  useFrame((state, delta) => {
    if (dragged) {
      vec.set(state.pointer.x, state.pointer.y, 0.5).unproject(state.camera);
      dir.copy(vec).sub(state.camera.position).normalize();
      vec.add(dir.multiplyScalar(state.camera.position.length()));
      [card, j1, j2, j3, fixed].forEach((ref) => ref.current?.wakeUp());
      card.current?.setNextKinematicTranslation({
        x: vec.x - dragged.x,
        y: vec.y - dragged.y,
        z: vec.z - dragged.z,
      });
    }
    if (!fixed.current) return;
    [j1, j2].forEach((ref) => {
      const lerped = lerpedOf(ref.current);
      const distance = Math.max(
        0.1,
        Math.min(1, lerped.distanceTo(ref.current.translation())),
      );
      lerped.lerp(
        ref.current.translation(),
        delta * (minSpeed + distance * (maxSpeed - minSpeed)),
      );
    });
    curve.points[0].copy(j3.current.translation());
    curve.points[1].copy(lerpedOf(j2.current));
    curve.points[2].copy(lerpedOf(j1.current));
    curve.points[3].copy(fixed.current.translation());
    band.current.geometry.setPoints(curve.getPoints(32));
    ang.copy(card.current.angvel());
    rot.copy(card.current.rotation());
    card.current.setAngvel(
      { x: ang.x, y: ang.y - rot.y * 0.25, z: ang.z },
      true,
    );
  });

  curve.curveType = "chordal";
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;

  return (
    <>
      <group position={[0, anchorY, 0]}>
        <RigidBody ref={fixed} {...segmentProps} type="fixed" />
        <RigidBody position={[0.5, 0, 0]} ref={j1} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody position={[1, 0, 0]} ref={j2} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody position={[1.5, 0, 0]} ref={j3} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody
          position={[2, 0, 0]}
          ref={card}
          {...segmentProps}
          type={dragged ? "kinematicPosition" : "dynamic"}
        >
          <CuboidCollider args={[0.8, 1.125, 0.01]} />
          <group
            scale={2.25}
            position={[0, -1.2, -0.05]}
            onPointerOver={() => hover(true)}
            onPointerOut={() => hover(false)}
            onPointerUp={(event: ThreeEvent<PointerEvent>) => {
              (event.target as Element).releasePointerCapture(event.pointerId);
              drag(false);
            }}
            onPointerDown={(event: ThreeEvent<PointerEvent>) => {
              (event.target as Element).setPointerCapture(event.pointerId);
              drag(
                new THREE.Vector3()
                  .copy(event.point)
                  .sub(vec.copy(card.current.translation())),
              );
            }}
          >
            <mesh geometry={nodes.card.geometry}>
              <meshPhysicalMaterial
                map={cardMap}
                map-anisotropy={16}
                clearcoat={1}
                clearcoatRoughness={0.15}
                roughness={0.9}
                metalness={0.8}
              />
            </mesh>
            <mesh
              geometry={nodes.clip.geometry}
              material={materials.metal}
              material-roughness={0.3}
            />
            <mesh geometry={nodes.clamp.geometry} material={materials.metal} />
          </group>
        </RigidBody>
      </group>
      <mesh ref={band}>
        <meshLineGeometry />
        <meshLineMaterial
          args={[{} as ConstructorParameters<typeof MeshLineMaterial>[0]]}
          color="white"
          depthTest={false}
          resolution={[1000, 1000]}
          useMap={1}
          map={texture}
          repeat={[-4, 1]}
          lineWidth={1}
        />
      </mesh>
    </>
  );
}
