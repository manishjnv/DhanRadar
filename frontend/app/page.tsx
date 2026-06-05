export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        fontFamily: "system-ui, sans-serif",
        background: "#0f172a",
        color: "#f8fafc",
      }}
    >
      <h1 style={{ fontSize: "3rem", fontWeight: 700, margin: 0 }}>
        DhanRadar
      </h1>
      <p style={{ marginTop: "1rem", color: "#94a3b8", fontSize: "1.25rem" }}>
        AI-powered Indian mutual fund &amp; stock radar
      </p>
      <p style={{ marginTop: "2rem", color: "#475569", fontSize: "0.875rem" }}>
        Phase 1 skeleton — UI coming in Phase 2+
      </p>
    </main>
  );
}
