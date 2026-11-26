import { stopContainer } from "./home-assistant";

export default function globalTeardown(): void {
  // KEEP=1 leaves the last language running, to look around in it or work
  // on a shot.
  if (!process.env.KEEP) {
    stopContainer();
  }
}
