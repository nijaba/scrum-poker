import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/space-grotesk/700.css";
import "./app.css";

import { mount } from "svelte";
import App from "./App.svelte";
import { applyDeck } from "./lib/deck";

applyDeck(document);

mount(App, { target: document.getElementById("app")! });
