<script setup lang="ts">
/**
 * Upload (A pattern). IMPLEMENTATION.md §2 pattern A.
 *
 * Phase 8 part 4: minimum-viable end-to-end upload chain.
 *   1. User picks a video file + fills code/title
 *   2. POST /v1/sessions to create the session row
 *   3. POST /v1/gcs/upload-url to get a signed PUT URL
 *   4. PUT the file directly to GCS (no proxy through our backend)
 *   5. POST /v1/gcs/upload-complete to register the Source
 *   6. Navigate to /s/:id
 *
 * Full pipeline (manifest parse, ingest enqueue, transcribe, etc.) lands
 * in Phase 6 / U37-U45.
 */
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { sessions as sessionsApi, gcs as gcsApi } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const router = useRouter();

const code = ref('');
const title = ref('');
const presenter = ref('');
const videoFile = ref<File | null>(null);
const progress = ref<string | null>(null);
const isUploading = ref(false);
const error = ref<string | null>(null);

function onFile(e: Event): void {
  const f = (e.target as HTMLInputElement).files?.[0];
  videoFile.value = f ?? null;
}

async function submit(): Promise<void> {
  if (!code.value || !title.value || !videoFile.value) return;
  isUploading.value = true;
  error.value = null;
  try {
    progress.value = 'Creating session…';
    const session = await sessionsApi.create({
      code: code.value.trim(),
      title: title.value.trim(),
      presenter: presenter.value.trim() || undefined,
      duration_sec: undefined,
    });

    progress.value = 'Requesting signed upload URL…';
    const signed = await gcsApi.signedUrl(session.id, videoFile.value.name, 'video');

    progress.value = `Uploading to GCS (${(videoFile.value.size / 1024 / 1024).toFixed(1)} MB)…`;
    const putResp = await fetch(signed.signed_url, {
      method: 'PUT',
      body: videoFile.value,
      headers: { 'Content-Type': videoFile.value.type || 'video/mp4' },
    });
    if (!putResp.ok) throw new Error(`GCS upload failed: HTTP ${putResp.status}`);

    progress.value = 'Registering upload…';
    await gcsApi.uploadComplete(session.id, [{
      gcs_uri: signed.gcs_uri,
      role: 'video',
      filename: videoFile.value.name,
      content_type: videoFile.value.type,
      size_bytes: videoFile.value.size,
    }]);

    toast.push(`Session ${code.value} created`, { tone: 'success' });
    router.push(`/s/${session.id}`);
  } catch (e) {
    if (e instanceof ApiError) error.value = `${e.status}: ${typeof e.body === 'string' ? e.body : JSON.stringify(e.body)}`;
    else error.value = e instanceof Error ? e.message : 'Upload failed';
  } finally {
    isUploading.value = false;
    progress.value = null;
  }
}
</script>

<template>
  <div class="upload">
    <header style="text-align: center; max-width: 720px; margin: 0 auto var(--space-6);">
      <h1 style="margin: 0 0 var(--space-2); font-size: var(--fs-2xl); font-weight: var(--fw-extrabold);">
        Upload a new session
      </h1>
      <p style="margin: 0; color: var(--fg2); font-size: var(--fs-sm);">
        Drops the video into GCS, registers a session row, and queues ingest.
        Full pipeline (manifest parse + STT + AI mode) lands in Phase 6.
      </p>
    </header>

    <form class="card upload__form" @submit.prevent="submit">
      <div class="upload__row">
        <label class="upload__field">
          <span>Session code</span>
          <input v-model="code" type="text" required placeholder="VIN-2026-004" :disabled="isUploading" />
        </label>
        <label class="upload__field">
          <span>Presenter (optional)</span>
          <input v-model="presenter" type="text" placeholder="Dr. Jane Smith" :disabled="isUploading" />
        </label>
      </div>

      <label class="upload__field">
        <span>Title</span>
        <input v-model="title" type="text" required placeholder="Approach to feline anemia" :disabled="isUploading" />
      </label>

      <label class="upload__field">
        <span>Video file (mp4 / mov)</span>
        <input type="file" accept="video/*" required :disabled="isUploading" @change="onFile" />
        <small v-if="videoFile" style="color: var(--fg2); font-size: var(--fs-xs);">
          {{ videoFile.name }} · {{ (videoFile.size / 1024 / 1024).toFixed(1) }} MB
        </small>
      </label>

      <p v-if="progress" style="color: var(--fg2); font-size: var(--fs-sm);">{{ progress }}</p>
      <p v-if="error" style="color: var(--color-red); font-size: var(--fs-sm);">{{ error }}</p>

      <div style="display: flex; gap: var(--space-2); justify-content: flex-end;">
        <button type="button" class="btn" :disabled="isUploading" @click="router.push('/sessions')">Cancel</button>
        <button
          type="submit"
          class="btn btn--primary"
          :disabled="isUploading || !code || !title || !videoFile"
          data-test-id="upload-submit"
        >
          {{ isUploading ? 'Uploading…' : 'Upload + Process' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.upload { padding: var(--space-6) var(--space-5); }
.upload__form {
  max-width: 720px; margin: 0 auto;
  display: flex; flex-direction: column; gap: var(--space-4);
}
.upload__row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.upload__field { display: flex; flex-direction: column; gap: var(--space-1); }
.upload__field > span { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--fg2); }
.upload__field input {
  padding: var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  font-family: var(--font-family); font-size: var(--fs-sm);
  background: var(--surface-card); color: var(--fg1);
}
.upload__field input[type="file"] { padding: var(--space-2); }
@media (max-width: 720px) { .upload__row { grid-template-columns: 1fr; } }
</style>
