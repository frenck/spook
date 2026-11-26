import { LANGUAGE, setUp } from "./home-assistant";

export default async function globalSetup(): Promise<void> {
  await setUp(LANGUAGE);
}
