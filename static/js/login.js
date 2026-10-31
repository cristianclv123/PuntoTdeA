document.getElementById("toggle-password")?.addEventListener("click", () => {
  const input = document.getElementById("password");
  if (!input) return;
  const visible = input.type === "text";
  input.type = visible ? "password" : "text";
});
