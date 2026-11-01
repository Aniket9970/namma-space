/**
 * frontend/src/types.ts
 * Type definitions and data contracts for Namma Space 3D Web Viewer.
 */

export interface Vector3Array extends Array<number> {
  0: number;
  1: number;
  2: number;
}

export interface QuaternionArray extends Array<number> {
  0: number;
  1: number;
  2: number;
  3: number;
}

export interface PanoMeta {
  type: 'equirect';
  url: string;
  lod_url?: string;
  depth_url?: string;
}

export interface TourNode {
  id: string;
  name?: string;
  position: [number, number, number];
  rotation: [number, number, number, number];
  pano: PanoMeta;
  neighbors: string[];
}

export interface TourManifest {
  meta: {
    units: 'm';
    up: 'Y';
    floor_y: number;
    scale_method: 'reference' | 'arcore' | 'colmap_relative' | 'vggt_relative';
    scale_factor?: number;
    transform_matrix?: number[][];
    floor_flatness_std_m?: number;
  };
  nodes: TourNode[];
  proxy_mesh: string;
  navmesh: string;
  navgrid: string;
  default_node?: string;
}

export interface NavGridData {
  resolution_m: number;
  origin: [number, number];
  width: number;
  height: number;
  data: number[]; // 0 = free, 1 = obstacle, 2 = unknown
  inflation_m: number;
  floor_y: number;
}

export interface POIItem {
  id: string;
  name: string;
  category: string;
  aliases: string[];
  position: [number, number, number];
  node_id?: string;
  source: 'manual' | 'detected';
}

export type ViewerMode = 'photosphere' | 'freeroam' | 'dollhouse' | 'splat';

