import { createApp } from 'vue';
import { createPinia } from 'pinia';

// Real CSS files from the React prototype (frontend/src/styles/ — kept verbatim)
import './styles/colors_and_type.css';
import './styles/app.css';
import './styles/wiring.css';
import './styles/settings.css';
import './styles/login.css';

import App from './App.vue';
import { router } from './router';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
