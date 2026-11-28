import "./assets/main.css";
import ui from "@nuxt/ui/vue-plugin";
import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import { routes } from "vue-router/auto-routes";
import App from "./App.vue";

const router = createRouter({
  // In the hash, so the panel's own pages never collide with the URL
  // Home Assistant shows for it.
  history: createWebHashHistory(),
  routes,
});

createApp(App).use(router).use(ui).mount("#app");
