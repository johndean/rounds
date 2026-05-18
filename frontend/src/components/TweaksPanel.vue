<script setup lang="ts">
/**
 * Tweaks panel — faithful Vue port of docs/port-source/tweaks-panel.jsx
 * (TweaksPanel + TweakSection + TweakToggle + TweakRadio + TweakButton).
 *
 * Differences from the React source (intentional, documented):
 *  - postMessage / Omelette host integration removed (Rounds isn't embedded
 *    in deck-stage). The standalone draggable panel + sections are preserved.
 *  - Open toggle: ⌘. (Cmd/Ctrl + period) toggles visibility — same as React.
 *
 * Sections are passed via <slot> from App.vue so the parent owns state.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue';

withDefaults(defineProps<{
  title?: string;
}>(), { title: 'Tweaks' });

const open = ref(false);
const dragRef = ref<HTMLDivElement | null>(null);
const offset = ref({ x: 16, y: 16 });
const PAD = 16;

function clampToViewport(): void {
  const panel = dragRef.value;
  if (!panel) return;
  const w = panel.offsetWidth, h = panel.offsetHeight;
  const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
  const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
  offset.value = {
    x: Math.min(maxRight, Math.max(PAD, offset.value.x)),
    y: Math.min(maxBottom, Math.max(PAD, offset.value.y)),
  };
}

function onDragStart(e: MouseEvent): void {
  const panel = dragRef.value;
  if (!panel) return;
  const r = panel.getBoundingClientRect();
  const sx = e.clientX, sy = e.clientY;
  const startRight = window.innerWidth - r.right;
  const startBottom = window.innerHeight - r.bottom;
  const move = (ev: MouseEvent): void => {
    offset.value = {
      x: startRight - (ev.clientX - sx),
      y: startBottom - (ev.clientY - sy),
    };
    clampToViewport();
  };
  const up = (): void => {
    window.removeEventListener('mousemove', move);
    window.removeEventListener('mouseup', up);
  };
  window.addEventListener('mousemove', move);
  window.addEventListener('mouseup', up);
}

function onKey(e: KeyboardEvent): void {
  if ((e.metaKey || e.ctrlKey) && e.key === '.') {
    e.preventDefault();
    open.value = !open.value;
  }
  if (e.key === 'Escape' && open.value) open.value = false;
}

onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => window.removeEventListener('keydown', onKey));

const panelStyle = computed(() => ({
  right: offset.value.x + 'px',
  bottom: offset.value.y + 'px',
}));
</script>

<template>
  <button
    v-if="!open"
    class="twk-fab"
    title="Open Tweaks (⌘.)"
    @click="open = true"
  >⚙</button>
  <div
    v-if="open"
    ref="dragRef"
    class="twk-panel"
    :style="panelStyle"
  >
    <div class="twk-hd" @mousedown="onDragStart">
      <b>{{ title }}</b>
      <button
        class="twk-x"
        aria-label="Close tweaks"
        @mousedown.stop
        @click="open = false"
      >✕</button>
    </div>
    <div class="twk-body">
      <slot />
    </div>
  </div>
</template>

<style>
.twk-fab {
  position: fixed; bottom: 16px; right: 16px; z-index: 800;
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--surface-card); color: var(--fg2);
  border: 1px solid var(--border-subtle);
  font-size: 16px; cursor: pointer; opacity: 0.6;
  box-shadow: 0 4px 12px rgba(0,0,0,0.10);
  transition: opacity var(--duration-fast) var(--easing-out);
}
.twk-fab:hover { opacity: 1; }

.twk-panel {
  position: fixed; z-index: 850;
  width: 280px; max-height: 70vh; overflow: hidden;
  display: flex; flex-direction: column;
  background: #0B1626; color: #E8EEF6;
  border-radius: var(--radius-md);
  box-shadow: 0 20px 50px rgba(0,0,0,0.40);
  font-family: var(--font-family); font-size: 12px;
}
.twk-hd {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; cursor: move; user-select: none;
  background: rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.06);
}
.twk-hd b { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: #B1C9E8; }
.twk-x {
  background: transparent; border: none; color: rgba(255,255,255,0.6);
  font-size: 14px; cursor: pointer; padding: 0 4px; line-height: 1;
}
.twk-x:hover { color: #fff; }
.twk-body { padding: 8px 0 14px; overflow-y: auto; }

.twk-sect {
  padding: 12px 14px 6px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: #6FA9F0;
}

.twk-row { padding: 4px 14px; }
.twk-row__lbl { font-size: 11px; color: #B1C9E8; margin-bottom: 4px; font-weight: 600; }
.twk-row__ctrl { display: flex; align-items: center; gap: 6px; }

.twk-toggle {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 14px; cursor: pointer;
}
.twk-toggle__lbl { font-size: 12px; color: #E8EEF6; }
.twk-toggle__sw {
  width: 32px; height: 18px; border-radius: 999px;
  background: rgba(255,255,255,0.12); border: none; padding: 0;
  position: relative; cursor: pointer;
  transition: background var(--duration-fast) var(--easing-out);
}
.twk-toggle__sw.is-on { background: var(--color-green); }
.twk-toggle__knob {
  position: absolute; top: 2px; left: 2px;
  width: 14px; height: 14px; border-radius: 50%; background: #fff;
  transition: left var(--duration-fast) var(--easing-out);
}
.twk-toggle__sw.is-on .twk-toggle__knob { left: 16px; }

.twk-radio { padding: 6px 14px; }
.twk-radio__lbl { font-size: 11px; color: #B1C9E8; margin-bottom: 4px; font-weight: 600; }
.twk-radio__row { display: flex; gap: 4px; }
.twk-radio__opt {
  flex: 1; padding: 5px 8px; border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.05); border: 1px solid transparent;
  color: rgba(255,255,255,0.7); cursor: pointer; font-size: 11px;
  font-family: inherit;
  transition: all var(--duration-fast) var(--easing-out);
}
.twk-radio__opt.is-active {
  background: rgba(8,97,206,0.25); color: #fff; border-color: rgba(8,97,206,0.6);
}
.twk-radio__opt:hover:not(.is-active) { background: rgba(255,255,255,0.10); }

.twk-btn {
  display: block; width: calc(100% - 28px); margin: 4px 14px;
  padding: 6px 10px; border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.10);
  color: #E8EEF6; font-size: 11.5px; font-family: inherit; text-align: left;
  cursor: pointer; transition: background var(--duration-fast) var(--easing-out);
}
.twk-btn:hover { background: rgba(255,255,255,0.16); }
</style>
