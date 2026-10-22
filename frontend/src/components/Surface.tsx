import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { Matrix } from '../types';
import { color } from '../lib/science';

export default function Surface({ field, low, high }: { field: Matrix; low: number; high: number }) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true }); }
    catch { setError('WebGL is unavailable. The 2D scientific heatmaps remain available.'); return; }
    const scene = new THREE.Scene(); scene.background = new THREE.Color('#15191d');
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100); camera.position.set(1.9, 1.8, 2.2);
    const controls = new OrbitControls(camera, renderer.domElement); controls.target.set(0, 0.15, 0); controls.enableDamping = true;
    const n = field.length, geometry = new THREE.PlaneGeometry(1.6, 1.6, n-1, n-1), vertices = geometry.attributes.position;
    const colors: number[] = [];
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const value = field[n-1-y][x]; vertices.setZ(y*n+x, (value-low)/Math.max(1e-12, high-low)*0.7);
      colors.push(...color(value, low, high).map(c => c/255));
    }
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); geometry.computeVertexNormals();
    const material = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(geometry, material); mesh.rotation.x = -Math.PI/2; scene.add(mesh);
    const grid = new THREE.GridHelper(2.2, 11, '#3a424b', '#252c33'); grid.position.y = -0.015; scene.add(grid);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); element.appendChild(renderer.domElement);
    const resize = new ResizeObserver(() => { renderer.setSize(element.clientWidth, element.clientHeight); camera.aspect = element.clientWidth/Math.max(1, element.clientHeight); camera.updateProjectionMatrix(); }); resize.observe(element);
    let frame = 0;
    const draw = () => { controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(draw); }; draw();
    return () => { cancelAnimationFrame(frame); resize.disconnect(); controls.dispose(); geometry.dispose(); material.dispose(); grid.geometry.dispose(); (grid.material as THREE.Material).dispose(); renderer.dispose(); renderer.domElement.remove(); };
  }, [field, low, high]);
  return <div className="surface-wrap"><div ref={host} className="surface-host"/>{error && <p className="error-message">{error}</p>}<div className="surface-caption">Drag to orbit · scroll to zoom · height scaled to shared temperature range</div></div>;
}
