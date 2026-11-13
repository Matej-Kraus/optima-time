import { cs } from "./i18n/cs";

export default function App() {
  return (
    <main className="app">
      <h1>{cs.appName}</h1>
      <p>{cs.placeholder}</p>
    </main>
  );
}
