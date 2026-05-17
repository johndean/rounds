import { createApp } from 'vue';
import { createPinia } from 'pinia';

import './styles/colors_and_type.css';
import './styles/app.css';
import './styles/wiring.css';
import './styles/settings.css';

import App from './App.vue';
import { router } from './router';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
