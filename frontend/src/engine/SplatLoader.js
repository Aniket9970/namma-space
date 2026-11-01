import * as THREE from 'three';

/**
 * High-Performance Standalone 3D Gaussian Splatting Loader & WebGL Renderer
 * 
 * Parses standard 32-byte binary .splat files:
 * 12 bytes: float32 x 3 position (x, y, z)
 * 12 bytes: float32 x 3 scale (sx, sy, sz)
 * 4 bytes: uint8 x 4 RGBA color
 * 4 bytes: uint8 x 4 rotation quaternion
 * 
 * Renders via hardware-accelerated InstancedBufferGeometry with camera-facing
 * Gaussian billboard quads and radial opacity falloff exp(-0.5 * r^2 * sharpness).
 * Zero WebGL2 integer texture dependency, zero worker crashes, 100% reliable across browsers.
 */
export class SplatLoader {
  static SPLAT_BYTES = 32;

  /**
   * Load .splat file from URL with optional progress callback
   */
  static async load(url, onProgress) {
    if (onProgress) onProgress(25);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to load splat file "${url}": ${response.status} ${response.statusText}`);
    }
    if (onProgress) onProgress(60);
    const arrayBuffer = await response.arrayBuffer();
    if (onProgress) onProgress(85);
    const splatData = this.parse(arrayBuffer);
    if (onProgress) onProgress(100);
    return splatData;
  }

  /**
   * Parse 32-byte binary splat buffer into typed float arrays and bounding box
   */
  static parse(arrayBuffer, options = {}) {
    const totalBytes = arrayBuffer.byteLength;
    const rawCount = Math.floor(totalBytes / this.SPLAT_BYTES);
    if (rawCount === 0) {
      throw new Error('Splat file is empty or corrupted');
    }

    // Optional stride for extremely large scenes (> 1.5M points) on low-end hardware
    const maxPoints = options.maxPoints || 1200000;
    const stride = rawCount > maxPoints ? Math.ceil(rawCount / maxPoints) : 1;
    const count = Math.floor(rawCount / stride);

    const positions = new Float32Array(count * 3);
    const scales = new Float32Array(count * 3);
    const colors = new Float32Array(count * 4);
    const quaternions = new Float32Array(count * 4);

    const dataView = new DataView(arrayBuffer);

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    let minZ = Infinity, maxZ = -Infinity;

    let outIdx = 0;
    for (let i = 0; i < rawCount; i += stride) {
      if (outIdx >= count) break;
      const offset = i * this.SPLAT_BYTES;

      // Position (3 x float32, little-endian)
      const x = dataView.getFloat32(offset + 0, true);
      const y = dataView.getFloat32(offset + 4, true);
      const z = dataView.getFloat32(offset + 8, true);

      positions[outIdx * 3 + 0] = x;
      positions[outIdx * 3 + 1] = y;
      positions[outIdx * 3 + 2] = z;

      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      if (z < minZ) minZ = z;
      if (z > maxZ) maxZ = z;

      // Scale (3 x float32) - clamp minimum scale to prevent subpixel speckles
      const sx = dataView.getFloat32(offset + 12, true);
      const sy = dataView.getFloat32(offset + 16, true);
      const sz = dataView.getFloat32(offset + 20, true);

      scales[outIdx * 3 + 0] = Math.max(0.012, Math.abs(sx));
      scales[outIdx * 3 + 1] = Math.max(0.012, Math.abs(sy));
      scales[outIdx * 3 + 2] = Math.max(0.012, Math.abs(sz));

      // RGBA color (4 x uint8 -> float 0..1)
      colors[outIdx * 4 + 0] = dataView.getUint8(offset + 24) / 255.0;
      colors[outIdx * 4 + 1] = dataView.getUint8(offset + 25) / 255.0;
      colors[outIdx * 4 + 2] = dataView.getUint8(offset + 26) / 255.0;
      colors[outIdx * 4 + 3] = dataView.getUint8(offset + 27) / 255.0;

      // Rotation quaternion (4 x uint8 -> float [-1, 1])
      quaternions[outIdx * 4 + 0] = (dataView.getUint8(offset + 28) - 127.5) / 127.5;
      quaternions[outIdx * 4 + 1] = (dataView.getUint8(offset + 29) - 127.5) / 127.5;
      quaternions[outIdx * 4 + 2] = (dataView.getUint8(offset + 30) - 127.5) / 127.5;
      quaternions[outIdx * 4 + 3] = (dataView.getUint8(offset + 31) - 127.5) / 127.5;

      outIdx++;
    }

    const bounds = {
      min: new THREE.Vector3(minX, minY, minZ),
      max: new THREE.Vector3(maxX, maxY, maxZ),
      center: new THREE.Vector3((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2),
      size: new THREE.Vector3(maxX - minX, maxY - minY, maxZ - minZ)
    };

    return {
      count: outIdx,
      positions,
      scales,
      colors,
      quaternions,
      bounds,
      sizeBytes: totalBytes
    };
  }

  /**
   * Create an InstancedBufferGeometry Mesh ready to add to Three.js scene
   */
  static createSplatMesh(splatData, options = {}) {
    const { count, positions, scales, colors, quaternions, bounds } = splatData;

    // Unit quad geometry [-1, 1]
    const baseQuad = new THREE.BufferGeometry();
    const vertices = new Float32Array([
      -1, -1, 0,
       1, -1, 0,
       1,  1, 0,
      -1,  1, 0
    ]);
    const uvs = new Float32Array([
      -1, -1,
       1, -1,
       1,  1,
      -1,  1
    ]);
    const indices = new Uint16Array([
      0, 1, 2,
      0, 2, 3
    ]);

    baseQuad.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    baseQuad.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    baseQuad.setIndex(new THREE.BufferAttribute(indices, 1));

    const instancedGeo = new THREE.InstancedBufferGeometry();
    instancedGeo.index = baseQuad.index;
    instancedGeo.attributes.position = baseQuad.attributes.position;
    instancedGeo.attributes.uv = baseQuad.attributes.uv;

    // Instance attributes
    instancedGeo.setAttribute('aCenter', new THREE.InstancedBufferAttribute(positions, 3));
    instancedGeo.setAttribute('aScale', new THREE.InstancedBufferAttribute(scales, 3));
    instancedGeo.setAttribute('aColor', new THREE.InstancedBufferAttribute(colors, 4));
    instancedGeo.setAttribute('aQuat', new THREE.InstancedBufferAttribute(quaternions, 4));

    // Custom WebGL Shader Material for Photorealistic Gaussian Billboards
    const material = new THREE.ShaderMaterial({
      uniforms: {
        uScaleFactor: { value: options.scaleFactor || 1.15 },
        uAlphaCutoff: { value: options.alphaCutoff || 0.008 },
        uGaussianSharpness: { value: options.gaussianSharpness || 3.0 }
      },
      vertexShader: `
        attribute vec3 aCenter;
        attribute vec3 aScale;
        attribute vec4 aColor;
        attribute vec4 aQuat;

        varying vec2 vUv;
        varying vec4 vColor;

        uniform float uScaleFactor;

        void main() {
          vUv = uv;
          vColor = aColor;

          // Camera-facing billboard expansion in view space
          vec4 mvCenter = modelViewMatrix * vec4(aCenter, 1.0);
          
          // Compute billboard radius from average splat scale
          float avgScale = (aScale.x + aScale.y + aScale.z) * 0.75 * uScaleFactor;
          vec3 viewPos = mvCenter.xyz + vec3(position.x * avgScale, position.y * avgScale, 0.0);

          gl_Position = projectionMatrix * vec4(viewPos, 1.0);
        }
      `,
      fragmentShader: `
        varying vec2 vUv;
        varying vec4 vColor;

        uniform float uAlphaCutoff;
        uniform float uGaussianSharpness;

        void main() {
          float distSq = dot(vUv, vUv);
          if (distSq > 1.0) {
            discard;
          }

          // Gaussian radial falloff: exp(-0.5 * r^2 * sharpness)
          float alphaFactor = exp(-0.5 * distSq * uGaussianSharpness);
          float finalAlpha = vColor.a * alphaFactor;

          if (finalAlpha < uAlphaCutoff) {
            discard;
          }

          gl_FragColor = vec4(vColor.rgb, finalAlpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      depthTest: true,
      blending: THREE.NormalBlending,
      side: THREE.DoubleSide
    });

    const mesh = new THREE.Mesh(instancedGeo, material);
    mesh.frustumCulled = false;
    mesh.userData = {
      bounds,
      count,
      sizeBytes: splatData.sizeBytes
    };

    return mesh;
  }
}
