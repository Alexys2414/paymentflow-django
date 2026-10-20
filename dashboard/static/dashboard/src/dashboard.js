(() => {
  const storageKey = "paymentflow-theme";
  const root = document.documentElement;
  const resolveTheme = (mode) => mode === "system"
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : mode;

  const setTheme = (mode) => {
    root.dataset.theme = resolveTheme(mode);
    root.dataset.themeMode = mode;
    localStorage.setItem(storageKey, mode);
    document.querySelectorAll("[data-theme-option]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeOption === mode));
    });
  };

  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.addEventListener("click", () => setTheme(button.dataset.themeOption));
  });
  const initialMode = root.dataset.themeMode || localStorage.getItem(storageKey) || "system";
  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeOption === initialMode));
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if ((root.dataset.themeMode || "system") === "system") setTheme("system");
  });

  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const closeSidebar = () => {
    sidebar?.classList.add("-translate-x-full");
    overlay?.classList.add("hidden");
  };
  document.querySelector("[data-sidebar-toggle]")?.addEventListener("click", () => {
    sidebar?.classList.remove("-translate-x-full");
    overlay?.classList.remove("hidden");
  });
  overlay?.addEventListener("click", closeSidebar);
  document.querySelectorAll("[data-sidebar-close]").forEach((button) => button.addEventListener("click", closeSidebar));

  document.querySelectorAll("[data-toast]").forEach((toast) => {
    window.setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-0.5rem)";
      window.setTimeout(() => toast.remove(), 200);
    }, 4800);
  });

  document.querySelectorAll("form[data-submit-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const submit = form.querySelector("[type=submit]");
      if (submit && form.checkValidity()) {
        submit.disabled = true;
        submit.dataset.originalText = submit.textContent;
        submit.textContent = "Working…";
      }
    });
  });
})();
