import React, { useRef, useLayoutEffect } from 'react'
import * as THREE from 'three'
import { extend, useThree, useLoader, useFrame } from '@react-three/fiber'
import { shaderMaterial } from '@react-three/drei'

// ── Photorealistic 3D Gaussian Splatting Shader Material ──────────────────────
const SplatMaterial = shaderMaterial(
  {
    alphaTest: 0,
    viewport: new THREE.Vector2(1980, 1080),
    focal: 1000.0,
    centerAndScaleTexture: null,
    covAndColorTexture: null,
  },
  /* glsl vertex shader */ `
    precision highp sampler2D;
    precision highp usampler2D;
    out vec4 vColor;
    out vec3 vPosition;
    uniform vec2 resolution;
    uniform vec2 viewport;
    uniform float focal;
    attribute uint splatIndex;
    uniform sampler2D centerAndScaleTexture;
    uniform usampler2D covAndColorTexture;    

    vec2 unpackInt16(in uint value) {
      int v = int(value);
      int v0 = v >> 16;
      int v1 = (v & 0xFFFF);
      if((v & 0x8000) != 0)
        v1 |= 0xFFFF0000;
      return vec2(float(v1), float(v0));
    }

    void main () {
      ivec2 texSize = textureSize(centerAndScaleTexture, 0);
      ivec2 texPos = ivec2(splatIndex%uint(texSize.x), splatIndex/uint(texSize.x));
      vec4 centerAndScaleData = texelFetch(centerAndScaleTexture, texPos, 0);
      vec4 center = vec4(centerAndScaleData.xyz, 1);
      vec4 camspace = modelViewMatrix * center;
      vec4 pos2d = projectionMatrix * camspace;

      float bounds = 1.2 * pos2d.w;
      if (pos2d.z < -pos2d.w || pos2d.x < -bounds || pos2d.x > bounds
        || pos2d.y < -bounds || pos2d.y > bounds) {
        gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
        return;
      }

      uvec4 covAndColorData = texelFetch(covAndColorTexture, texPos, 0);
      vec2 cov3D_M11_M12 = unpackInt16(covAndColorData.x) * centerAndScaleData.w;
      vec2 cov3D_M13_M22 = unpackInt16(covAndColorData.y) * centerAndScaleData.w;
      vec2 cov3D_M23_M33 = unpackInt16(covAndColorData.z) * centerAndScaleData.w;
      mat3 Vrk = mat3(
        cov3D_M11_M12.x, cov3D_M11_M12.y, cov3D_M13_M22.x,
        cov3D_M11_M12.y, cov3D_M13_M22.y, cov3D_M23_M33.x,
        cov3D_M13_M22.x, cov3D_M23_M33.x, cov3D_M23_M33.y
      );

      mat3 J = mat3(
        focal / camspace.z, 0., -(focal * camspace.x) / (camspace.z * camspace.z),
        0., focal / camspace.z, -(focal * camspace.y) / (camspace.z * camspace.z),
        0., 0., 0.
      );

      mat3 W = transpose(mat3(modelViewMatrix));
      mat3 T = W * J;
      mat3 cov = transpose(T) * Vrk * T;
      vec2 vCenter = vec2(pos2d) / pos2d.w;
      float diagonal1 = cov[0][0] + 0.3;
      float offDiagonal = cov[0][1];
      float diagonal2 = cov[1][1] + 0.3;
      float mid = 0.5 * (diagonal1 + diagonal2);
      float radius = length(vec2((diagonal1 - diagonal2) / 2.0, offDiagonal));
      float lambda1 = mid + radius;
      float lambda2 = max(mid - radius, 0.1);
      vec2 diagDiff = vec2(offDiagonal, lambda1 - diagonal1);
      float dLen = length(diagDiff);
      vec2 diagonalVector = dLen > 0.0001 ? diagDiff / dLen : vec2(1.0, 0.0);
      vec2 v1 = min(sqrt(2.0 * max(lambda1, 0.001)), 1024.0) * diagonalVector;
      vec2 v2 = min(sqrt(2.0 * max(lambda2, 0.001)), 1024.0) * vec2(diagonalVector.y, -diagonalVector.x);
      uint colorUint = covAndColorData.w;
      vColor = vec4(
        float(colorUint & uint(0xFF)) / 255.0,
        float((colorUint >> uint(8)) & uint(0xFF)) / 255.0,
        float((colorUint >> uint(16)) & uint(0xFF)) / 255.0,
        float(colorUint >> uint(24)) / 255.0
      );
      vPosition = position;

      gl_Position = vec4(
        vCenter 
          + position.x * v2 / viewport * 2.0 
          + position.y * v1 / viewport * 2.0, pos2d.z / pos2d.w, 1.0);
    }
  `,
  /* glsl fragment shader */ `
    #include <alphatest_pars_fragment>
    in vec4 vColor;
    in vec3 vPosition;
    void main () {
      float A = -dot(vPosition.xy, vPosition.xy);
      if (A < -4.0) discard;
      float B = exp(A) * vColor.a;
      vec4 diffuseColor = vec4(vColor.rgb, B);
      #include <alphatest_fragment>
      gl_FragColor = diffuseColor;
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }
  `
)

// ── Web Worker for 16-bit Counting Depth Sorting ──────────────────────────────
function createSortWorker(self) {
  let matrices = null
  let offset = 0
  let depthList = null
  let sizeList = null
  let validIndexList = null
  const counts0 = new Uint32Array(256 * 256)
  const starts0 = new Uint32Array(256 * 256)

  function sortSplats(view) {
    const vertexCount = matrices.length / 16
    const threshold = -0.0001
    let maxDepth = -Infinity
    let minDepth = Infinity

    if (!depthList || depthList.length !== vertexCount) {
      depthList = new Float32Array(vertexCount)
      sizeList = new Int32Array(vertexCount)
      validIndexList = new Int32Array(vertexCount)
    }

    let validCount = 0

    for (let i = 0; i < vertexCount; i++) {
      const depth =
        view[0] * matrices[i * 16 + 12] +
        view[1] * matrices[i * 16 + 13] +
        view[2] * matrices[i * 16 + 14] +
        view[3]

      if (depth < 0 && matrices[i * 16 + 15] > threshold * depth) {
        depthList[validCount] = depth
        validIndexList[validCount] = i
        validCount++
        if (depth > maxDepth) maxDepth = depth
        if (depth < minDepth) minDepth = depth
      }
    }

    counts0.fill(0)
    const depthRange = maxDepth - minDepth
    const depthInv = depthRange > 0.00001 ? (256 * 256 - 1) / depthRange : 0
    for (let i = 0; i < validCount; i++) {
      let idx = ((depthList[i] - minDepth) * depthInv) | 0
      if (idx < 0) idx = 0
      else if (idx > 65535) idx = 65535
      sizeList[i] = idx
      counts0[idx]++
    }
    starts0[0] = 0
    for (let i = 1; i < 256 * 256; i++) starts0[i] = starts0[i - 1] + counts0[i - 1]
    const depthIndex = new Uint32Array(validCount)
    for (let i = 0; i < validCount; i++) depthIndex[starts0[sizeList[i]]++] = validIndexList[i]
    return depthIndex
  }

  self.onmessage = (e) => {
    if (e.data.method === 'push') {
      if (offset === 0) matrices = new Float32Array(e.data.length)
      const new_matrices = new Float32Array(e.data.matrices)
      matrices.set(new_matrices, offset)
      offset += new_matrices.length
    } else if (e.data.method === 'sort') {
      if (matrices !== null) {
        const indices = sortSplats(new Float32Array(e.data.view))
        self.postMessage({ indices, key: e.data.key }, [indices.buffer])
      }
    }
  }
}

// ── Vercel & Standalone Resilient Splat Loader ─────────────────────────────────
class RobustSplatLoader extends THREE.Loader {
  constructor(...args) {
    super(...args)
    this.gl = null
    this.chunkSize = 25000
    this.onProgress = null
  }

  load(url, onLoad, onProgress, onError) {
    const shared = {
      gl: this.gl,
      url: this.manager.resolveURL(url),
      worker: new Worker(
        URL.createObjectURL(
          new Blob(['(', createSortWorker.toString(), ')(self)'], {
            type: 'application/javascript',
          })
        )
      ),
      manager: this.manager,
      update: (target, camera) => update(camera, shared, target),
      connect: (target) => connect(shared, target),
      loading: false,
      loaded: false,
      loadedVertexCount: 0,
      chunkSize: this.chunkSize,
      totalDownloadBytes: 0,
      numVertices: 0,
      rowLength: 32, // 3 * 4 pos + 3 * 4 scale + 4 color + 4 quat = 32 bytes
      maxVertexes: 0,
      bufferTextureWidth: 0,
      bufferTextureHeight: 0,
      stream: null,
      fullBuffer: null,
      centerAndScaleData: null,
      covAndColorData: null,
      covAndColorTexture: null,
      centerAndScaleTexture: null,
      onProgress: onProgress || this.onProgress,
      onLoaded: this.onLoaded,
    }

    loadShared(shared)
      .then(onLoad)
      .catch((e) => {
        console.error('[RobustSplatLoader] Load failed:', e)
        if (onError) onError(e)
        shared.manager.itemError(shared.url)
      })
  }
}

async function loadShared(shared) {
  shared.manager.itemStart(shared.url)
  const data = await fetch(shared.url)
  if (!data.ok || data.body === null) {
    throw new Error(`Failed to fetch splat file "${shared.url}": ${data.status}`)
  }

  let totalDownloadBytes = 0
  const lenHeader = data.headers.get('Content-Length')
  if (lenHeader) {
    totalDownloadBytes = parseInt(lenHeader, 10) || 0
  }

  const reader = data.body.getReader()
  const chunks = []
  let bytesDownloaded = 0

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    bytesDownloaded += value.length
    if (shared.onProgress) {
      if (totalDownloadBytes > 0) {
        shared.onProgress({
          loaded: bytesDownloaded,
          total: totalDownloadBytes,
          percent: Math.min(99, Math.round((bytesDownloaded / totalDownloadBytes) * 100)),
        })
      } else {
        shared.onProgress({
          loaded: bytesDownloaded,
          total: 0,
          percent: Math.min(95, Math.round((bytesDownloaded / 1600000) * 100)),
        })
      }
    }
  }

  if (shared.onProgress) {
    shared.onProgress({
      loaded: bytesDownloaded,
      total: bytesDownloaded,
      percent: 100,
    })
  }

  const fullArray = new Uint8Array(bytesDownloaded)
  let offset = 0
  for (const chunk of chunks) {
    fullArray.set(chunk, offset)
    offset += chunk.length
  }
  chunks.length = 0

  shared.fullBuffer = fullArray.buffer
  shared.totalDownloadBytes = bytesDownloaded
  shared.numVertices = Math.floor(shared.totalDownloadBytes / shared.rowLength)

  const context = shared.gl.getContext()
  let maxTextureSize = context.getParameter(context.MAX_TEXTURE_SIZE)
  shared.maxVertexes = maxTextureSize * maxTextureSize
  if (shared.numVertices > shared.maxVertexes) shared.numVertices = shared.maxVertexes

  shared.bufferTextureWidth = maxTextureSize
  shared.bufferTextureHeight = Math.floor((shared.numVertices - 1) / maxTextureSize) + 1

  shared.centerAndScaleData = new Float32Array(shared.bufferTextureWidth * shared.bufferTextureHeight * 4)
  shared.covAndColorData = new Uint32Array(shared.bufferTextureWidth * shared.bufferTextureHeight * 4)

  shared.centerAndScaleTexture = new THREE.DataTexture(
    shared.centerAndScaleData,
    shared.bufferTextureWidth,
    shared.bufferTextureHeight,
    THREE.RGBAFormat,
    THREE.FloatType
  )
  shared.centerAndScaleTexture.needsUpdate = true

  shared.covAndColorTexture = new THREE.DataTexture(
    shared.covAndColorData,
    shared.bufferTextureWidth,
    shared.bufferTextureHeight,
    THREE.RGBAIntegerFormat,
    THREE.UnsignedIntType
  )
  shared.covAndColorTexture.internalFormat = 'RGBA32UI'
  shared.covAndColorTexture.needsUpdate = true

  return shared
}

async function ensureTextures(shared) {
  if (shared.gl && shared.gl.initTexture) {
    try {
      shared.gl.initTexture(shared.centerAndScaleTexture)
      shared.gl.initTexture(shared.covAndColorTexture)
    } catch (e) {
      console.warn('[RobustSplatLoader] initTexture fallback:', e)
    }
  }

  for (let i = 0; i < 40; i++) {
    const p1 = shared.gl.properties.get(shared.centerAndScaleTexture)
    const p2 = shared.gl.properties.get(shared.covAndColorTexture)
    if (p1?.__webglTexture && p2?.__webglTexture) return true
    await new Promise((r) => setTimeout(r, 16))
  }
  return false
}

async function lazyLoad(shared) {
  shared.loading = true

  await ensureTextures(shared)

  const vertexCount = Math.floor(shared.fullBuffer.byteLength / shared.rowLength)
  const matrices = pushDataBuffer(shared, shared.fullBuffer, vertexCount)
  shared.worker.postMessage(
    {
      method: 'push',
      src: shared.url,
      length: shared.numVertices * 16,
      matrices: matrices.buffer,
    },
    [matrices.buffer]
  )

  shared.loaded = true
  shared.manager.itemEnd(shared.url)
  if (typeof shared.onLoaded === 'function') {
    shared.onLoaded()
  }
}

function update(camera, shared, target) {
  camera.updateMatrixWorld()
  shared.gl.getCurrentViewport(target.viewport)
  target.material.viewport.x = target.viewport.z
  target.material.viewport.y = target.viewport.w
  target.material.focal = (target.viewport.w / 2.0) * Math.abs(camera.projectionMatrix.elements[5])

  if (target.ready) {
    target.ready = false
    const view = new Float32Array([
      target.modelViewMatrix.elements[2],
      -target.modelViewMatrix.elements[6],
      target.modelViewMatrix.elements[10],
      target.modelViewMatrix.elements[14],
    ])
    shared.worker.postMessage(
      {
        method: 'sort',
        src: shared.url,
        key: target.uuid,
        view: view.buffer,
      },
      [view.buffer]
    )
  }
}

function connect(shared, target) {
  if (!shared.loading) lazyLoad(shared)
  target.ready = false
  target.viewport = new THREE.Vector4()

  let splatIndexArray = new Uint32Array(shared.bufferTextureWidth * shared.bufferTextureHeight)
  const splatIndexes = new THREE.InstancedBufferAttribute(splatIndexArray, 1, false)
  splatIndexes.setUsage(THREE.DynamicDrawUsage)

  const geometry = (target.geometry = new THREE.InstancedBufferGeometry())
  const positionsArray = new Float32Array(6 * 3)
  const positions = new THREE.BufferAttribute(positionsArray, 3)
  geometry.setAttribute('position', positions)
  positions.setXYZ(2, -2.0, 2.0, 0.0)
  positions.setXYZ(1, 2.0, 2.0, 0.0)
  positions.setXYZ(0, -2.0, -2.0, 0.0)
  positions.setXYZ(5, -2.0, -2.0, 0.0)
  positions.setXYZ(4, 2.0, 2.0, 0.0)
  positions.setXYZ(3, 2.0, -2.0, 0.0)
  positions.needsUpdate = true

  geometry.setAttribute('splatIndex', splatIndexes)
  geometry.instanceCount = 1

  function listener(e) {
    if (target && e.data.key === target.uuid) {
      let indexes = new Uint32Array(e.data.indices)
      geometry.attributes.splatIndex.set(indexes)
      geometry.attributes.splatIndex.needsUpdate = true
      geometry.instanceCount = indexes.length
      target.ready = true
      if (typeof shared.onLoaded === 'function') {
        shared.onLoaded()
      }
    }
  }

  shared.worker.addEventListener('message', listener)

  async function wait() {
    while (true) {
      const p1 = shared.gl.properties.get(shared.centerAndScaleTexture)
      const p2 = shared.gl.properties.get(shared.covAndColorTexture)
      if (p1?.__webglTexture && p2?.__webglTexture && shared.loadedVertexCount > 0) break
      await new Promise((resolve) => setTimeout(resolve, 10))
    }
    target.ready = true
    if (typeof shared.onLoaded === 'function') {
      shared.onLoaded()
    }
  }
  wait()

  return () => shared.worker.removeEventListener('message', listener)
}

function pushDataBuffer(shared, buffer, vertexCount) {
  const context = shared.gl.getContext()
  if (shared.loadedVertexCount + vertexCount > shared.maxVertexes) {
    vertexCount = shared.maxVertexes - shared.loadedVertexCount
  }
  if (vertexCount <= 0) return new Float32Array(0)

  const u_buffer = new Uint8Array(buffer)
  const f_buffer = new Float32Array(buffer)
  const matrices = new Float32Array(vertexCount * 16)
  const covAndColorData_uint8 = new Uint8Array(shared.covAndColorData.buffer)
  const covAndColorData_int16 = new Int16Array(shared.covAndColorData.buffer)

  for (let i = 0; i < vertexCount; i++) {
    const quat = new THREE.Quaternion(
      -(u_buffer[32 * i + 28 + 1] - 128) / 128.0,
      (u_buffer[32 * i + 28 + 2] - 128) / 128.0,
      (u_buffer[32 * i + 28 + 3] - 128) / 128.0,
      -(u_buffer[32 * i + 28 + 0] - 128) / 128.0
    )
    quat.invert()

    const center = new THREE.Vector3(f_buffer[8 * i + 0], f_buffer[8 * i + 1], -f_buffer[8 * i + 2])
    const scale = new THREE.Vector3(f_buffer[8 * i + 3 + 0], f_buffer[8 * i + 3 + 1], f_buffer[8 * i + 3 + 2])

    const mtx = new THREE.Matrix4()
    mtx.makeRotationFromQuaternion(quat)
    mtx.transpose()
    mtx.scale(scale)
    const mtx_t = mtx.clone()
    mtx.transpose()
    mtx.premultiply(mtx_t)
    mtx.setPosition(center)

    const cov_indexes = [0, 1, 2, 5, 6, 10]
    let max_value = 0.0
    for (let j = 0; j < cov_indexes.length; j++) {
      if (Math.abs(mtx.elements[cov_indexes[j]]) > max_value) {
        max_value = Math.abs(mtx.elements[cov_indexes[j]])
      }
    }

    let destOffset = shared.loadedVertexCount * 4 + i * 4
    shared.centerAndScaleData[destOffset + 0] = center.x
    shared.centerAndScaleData[destOffset + 1] = -center.y
    shared.centerAndScaleData[destOffset + 2] = center.z
    shared.centerAndScaleData[destOffset + 3] = max_value / 32767.0

    destOffset = shared.loadedVertexCount * 8 + i * 4 * 2
    for (let j = 0; j < cov_indexes.length; j++) {
      covAndColorData_int16[destOffset + j] = (mtx.elements[cov_indexes[j]] * 32767.0) / max_value
    }

    // RGBA
    destOffset = shared.loadedVertexCount * 16 + (i * 4 + 3) * 4
    const col = new THREE.Color(
      u_buffer[32 * i + 24 + 0] / 255,
      u_buffer[32 * i + 24 + 1] / 255,
      u_buffer[32 * i + 24 + 2] / 255
    )
    col.convertSRGBToLinear()
    covAndColorData_uint8[destOffset + 0] = col.r * 255
    covAndColorData_uint8[destOffset + 1] = col.g * 255
    covAndColorData_uint8[destOffset + 2] = col.b * 255
    covAndColorData_uint8[destOffset + 3] = u_buffer[32 * i + 24 + 3]

    // Scale metric for depth sort
    mtx.elements[15] = (Math.max(scale.x, scale.y, scale.z) * u_buffer[32 * i + 24 + 3]) / 255.0
    for (let j = 0; j < 16; j++) matrices[i * 16 + j] = mtx.elements[j]
  }

  const p1 = shared.gl.properties.get(shared.centerAndScaleTexture)
  const p2 = shared.gl.properties.get(shared.covAndColorTexture)

  if (p1?.__webglTexture && p2?.__webglTexture) {
    while (vertexCount > 0) {
      let width = 0
      let height = 0
      const xoffset = shared.loadedVertexCount % shared.bufferTextureWidth
      const yoffset = Math.floor(shared.loadedVertexCount / shared.bufferTextureWidth)
      if (shared.loadedVertexCount % shared.bufferTextureWidth !== 0) {
        width = Math.min(shared.bufferTextureWidth, xoffset + vertexCount) - xoffset
        height = 1
      } else if (Math.floor(vertexCount / shared.bufferTextureWidth) > 0) {
        width = shared.bufferTextureWidth
        height = Math.floor(vertexCount / shared.bufferTextureWidth)
      } else {
        width = vertexCount % shared.bufferTextureWidth
        height = 1
      }

      context.bindTexture(context.TEXTURE_2D, p1.__webglTexture)
      context.texSubImage2D(
        context.TEXTURE_2D,
        0,
        xoffset,
        yoffset,
        width,
        height,
        context.RGBA,
        context.FLOAT,
        shared.centerAndScaleData,
        shared.loadedVertexCount * 4
      )

      context.bindTexture(context.TEXTURE_2D, p2.__webglTexture)
      context.texSubImage2D(
        context.TEXTURE_2D,
        0,
        xoffset,
        yoffset,
        width,
        height,
        context.RGBA_INTEGER,
        context.UNSIGNED_INT,
        shared.covAndColorData,
        shared.loadedVertexCount * 4
      )

      shared.gl.resetState()
      shared.loadedVertexCount += width * height
      vertexCount -= width * height
    }
  } else {
    // If textures are not yet bound, fallback: Three.js uploads data on frame render
    shared.centerAndScaleTexture.needsUpdate = true
    shared.covAndColorTexture.needsUpdate = true
    shared.loadedVertexCount += vertexCount
  }

  return matrices
}

// ── GaussianSplat Component ───────────────────────────────────────────────────
export default function GaussianSplat({
  src,
  alphaTest = 0.05,
  chunkSize = 25000,
  onLoaded,
  onProgress,
  ...props
}) {
  extend({ SplatMaterial })
  const ref = useRef(null)
  const gl = useThree((state) => state.gl)
  const camera = useThree((state) => state.camera)

  const shared = useLoader(RobustSplatLoader, src, (loader) => {
    loader.gl = gl
    loader.chunkSize = chunkSize
    loader.onProgress = onProgress
    loader.onLoaded = onLoaded
  })

  // Keep callback references synchronized on the shared loader object
  if (shared) {
    shared.onProgress = onProgress
    shared.onLoaded = onLoaded
  }

  useLayoutEffect(() => {
    const cleanup = shared.connect(ref.current)
    return cleanup
  }, [shared, src])

  React.useEffect(() => {
    if (shared && shared.loaded && onLoaded) {
      onLoaded()
    }
  }, [shared, shared?.loaded, onLoaded])

  useFrame(() => shared.update(ref.current, camera))

  return (
    <mesh ref={ref} frustumCulled={false} {...props}>
      <splatMaterial
        key={`${src}/${alphaTest}${SplatMaterial.key}`}
        transparent={true}
        depthTest={true}
        alphaTest={alphaTest}
        centerAndScaleTexture={shared.centerAndScaleTexture}
        covAndColorTexture={shared.covAndColorTexture}
        depthWrite={alphaTest > 0}
        blending={THREE.CustomBlending}
        blendSrcAlpha={THREE.OneFactor}
        toneMapped={false}
      />
    </mesh>
  )
}
