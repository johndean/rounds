/**
 * Rounds router — hash mode. Routes mirror IMPLEMENTATION.md §5 verbatim.
 *
 * | Hash              | View                  |
 * | ----------------- | --------------------- |
 * | #/login           | LoginView (public)    |
 * | #/dashboard       | DashboardView         |
 * | #/sessions        | SessionsView          |
 * | #/s/:id           | SessionDetailView     |
 * | #/upload          | UploadView            |
 * | #/e/:id           | EditorView            |
 * | #/e/:id/sop       | SopView               |
 * | #/e/:id/audit     | EditorAuditView       |
 * | #/v/:id           | ViewerView            |
 * | #/p/:id           | ProcessingView        |
 * | #/improvements    | ImprovementsView      |
 * | #/settings/:section? | SettingsView      |
 * | #/audit           | AuditView             |
 * | #/gcs             | GcsView               |
 */
import { createRouter, createWebHashHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login',               component: () => import('@/views/LoginView.vue'),           name: 'login',  meta: { public: true } },
    { path: '/dashboard',           component: () => import('@/views/DashboardView.vue'),       name: 'dashboard' },
    { path: '/sessions',            component: () => import('@/views/SessionsView.vue'),        name: 'sessions' },
    { path: '/s/:id',               component: () => import('@/views/SessionDetailView.vue'),   name: 'session-detail', props: true },
    { path: '/upload',              component: () => import('@/views/UploadView.vue'),          name: 'upload' },
    { path: '/e/:id',               component: () => import('@/views/EditorView.vue'),          name: 'editor', props: true },
    { path: '/e/:id/sop',           component: () => import('@/views/SopView.vue'),             name: 'sop', props: true },
    { path: '/e/:id/audit',         component: () => import('@/views/EditorAuditView.vue'),     name: 'editor-audit', props: true },
    { path: '/v/:id',               component: () => import('@/views/ViewerView.vue'),          name: 'viewer', props: true },
    { path: '/p/:id',               component: () => import('@/views/ProcessingView.vue'),      name: 'processing', props: true },
    { path: '/improvements',        component: () => import('@/views/ImprovementsView.vue'),    name: 'improvements' },
    { path: '/settings/:section?',  component: () => import('@/views/SettingsView.vue'),        name: 'settings', props: true },
    { path: '/audit',               component: () => import('@/views/AuditView.vue'),           name: 'audit' },
    { path: '/gcs',                 component: () => import('@/views/GcsView.vue'),             name: 'gcs' },
    { path: '/:catchAll(.*)',       redirect: '/dashboard' },
  ],
});

router.beforeEach((to, _from, next) => {
  if (to.meta.public) {
    next();
    return;
  }
  const auth = useAuthStore();
  if (auth.isAuthenticated) {
    next();
    return;
  }
  next({ name: 'login', query: { next: to.fullPath } });
});
