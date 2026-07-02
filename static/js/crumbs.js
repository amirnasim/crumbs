(function () {
  "use strict";

  var root = document.documentElement;

  function initMenuDrawer() {
    var toggle = document.getElementById("nav-toggle");
    var drawer = document.getElementById("menu-drawer");
    var backdrop = document.getElementById("menu-drawer-backdrop");
    var drawerDuration = 320;
    var mobileNavQuery = window.matchMedia("(max-width: 899px)");

    if (!toggle || !drawer || !backdrop) return;

    function isMobileNav() {
      return mobileNavQuery.matches;
    }

    function setDrawerOpen(isOpen) {
      if (!isMobileNav()) {
        isOpen = false;
      }

      drawer.classList.toggle("is-open", isOpen);
      backdrop.classList.toggle("is-open", isOpen);
      root.classList.toggle("drawer-open", isOpen);
      document.body.classList.toggle("menu-drawer-open", isOpen);

      drawer.setAttribute("aria-hidden", isOpen ? "false" : "true");
      backdrop.setAttribute("aria-hidden", isOpen ? "false" : "true");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      toggle.setAttribute("aria-label", isOpen ? "بستن منو" : "باز کردن منو");

      if (isOpen) {
        backdrop.removeAttribute("hidden");
        toggle.focus();
        return;
      }

      window.setTimeout(function () {
        if (!drawer.classList.contains("is-open")) {
          backdrop.setAttribute("hidden", "");
        }
      }, drawerDuration);
    }

    function openDrawer() {
      backdrop.removeAttribute("hidden");
      setDrawerOpen(true);
    }

    function closeDrawer() {
      setDrawerOpen(false);
      toggle.focus();
    }

    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();

      if (!isMobileNav()) {
        return;
      }

      if (drawer.classList.contains("is-open")) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });

    backdrop.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && drawer.classList.contains("is-open") && isMobileNav()) {
        event.preventDefault();
        closeDrawer();
      }
    });

    mobileNavQuery.addEventListener("change", function () {
      if (!isMobileNav()) {
        closeDrawer();
      }
    });

    drawer.querySelectorAll("a.menu-drawer__link").forEach(function (link) {
      link.addEventListener("click", closeDrawer);
    });
  }

  function initHeaderNavActive() {
    var links = document.querySelectorAll(".menu-drawer__link[data-nav], .header-nav__link[data-nav]");
    if (!links.length) return;

    function updateActive() {
      var path = window.location.pathname;
      var hash = window.location.hash.replace("#", "");

      links.forEach(function (link) {
        var matchPath = link.getAttribute("data-nav");
        var matchHash = link.getAttribute("data-nav-hash");
        var isActive = false;

        if (matchHash) {
          isActive =
            (path === "/shop" || path.indexOf("/shop/") === 0) && hash === matchHash;
        } else if (matchPath === "/") {
          isActive = path === "/";
        } else if (matchPath) {
          isActive = path === matchPath || path.indexOf(matchPath + "/") === 0;
        }

        link.classList.toggle("is-active", isActive);
      });
    }

    updateActive();
    window.addEventListener("hashchange", updateActive);
  }

  // Quantity controls on product detail
  document.querySelectorAll(".quantity-control").forEach(function (control) {
    var input = control.querySelector(".qty-input");
    if (!input) return;

    control.querySelectorAll(".qty-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var current = parseInt(input.value, 10) || 1;
        var min = parseInt(input.min, 10) || 1;
        var max = parseInt(input.max, 10) || 99;

        if (btn.dataset.action === "increase" && current < max) {
          input.value = current + 1;
        } else if (btn.dataset.action === "decrease" && current > min) {
          input.value = current - 1;
        }
      });
    });
  });

  // Header scroll effect — transparent over hero, solid on scroll
  var header = document.getElementById("site-header");
  var mainContent = document.getElementById("main-content");
  var homeScroll = document.getElementById("home-scroll");
  var isHomePage = document.body.classList.contains("page-home");
  var scrollRoot = isHomePage && homeScroll ? homeScroll : mainContent;
  var heroTrack = document.getElementById("hero-media-track");
  var heroMedia = document.querySelector(".hero-media");

  if (header && !isHomePage) {
    var updateHeaderScroll = function () {
      var scrolled = window.scrollY > 16;

      if (heroTrack) {
        scrolled = scrolled || heroTrack.scrollTop > 16;
      }

      if (heroMedia && window.scrollY >= heroMedia.offsetHeight - 8) {
        scrolled = true;
      }

      header.classList.toggle("is-scrolled", scrolled);
    };

    updateHeaderScroll();
    window.addEventListener("scroll", updateHeaderScroll, { passive: true });

    if (heroTrack) {
      heroTrack.addEventListener("scroll", updateHeaderScroll, { passive: true });
    }
  }

  // Motion — page load fade + section reveal
  var prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function initPageMotion() {
    root.classList.add("page-is-loaded");

    if (prefersReducedMotion) {
      document.querySelectorAll(".motion-reveal").forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    if (document.body.classList.contains("page-home")) {
      return;
    }

    document.querySelectorAll("main .section, main .page-hero").forEach(function (el) {
      el.classList.add("motion-reveal");
    });

    var revealTargets = document.querySelectorAll(".motion-reveal");
    if (!revealTargets.length) return;

    if (!("IntersectionObserver" in window)) {
      revealTargets.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    var motionRoot = isHomePage && scrollRoot ? scrollRoot : null;
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        });
      },
      {
        root: motionRoot,
        threshold: isHomePage ? 0.22 : 0.08,
        rootMargin: isHomePage ? "0px" : "0px 0px -4% 0px",
      }
    );

    revealTargets.forEach(function (el) {
      revealObserver.observe(el);
    });
  }

  function initHomePage() {
    if (!isHomePage) return;

    var heroScene = document.getElementById("story-scene-1");
    if (header && heroScene) {
      function updateHeader() {
        var past = Math.max(0, -heroScene.getBoundingClientRect().top);
        var blend = Math.min(1, past / (window.innerHeight * 0.14));

        header.style.setProperty("--header-solid", blend.toFixed(3));
        header.classList.toggle("is-scrolled", blend > 0.72);
      }

      updateHeader();
      window.addEventListener("scroll", updateHeader, { passive: true });
    }

    if (heroScene) {
      var heroVideo = heroScene.querySelector(".story-hero__video");
      if (heroVideo) {
        heroVideo.play().catch(function () {});
      }
    }
  }

  // Café menu — instant category switch with fade
  var MENU_SLUGS = ["cookies", "coffee", "food", "salads", "drinks"];
  var MENU_FETCH_SLUG = { food: "bakery" };

  function initCafeMenu() {
    var menu = document.querySelector(".cafe-menu");
    if (!menu) return;

    var tabs = menu.querySelectorAll(".menu-nav__tab");
    var panels = menu.querySelectorAll(".menu-panel");
    if (!tabs.length || !panels.length) return;

    var defaultSlug = menu.dataset.defaultCategory || "cookies";
    var hashSlug = window.location.hash.replace("#", "");
    var initialSlug = MENU_SLUGS.indexOf(hashSlug) !== -1 ? hashSlug : defaultSlug;

    function updatePanelEmpty(panel) {
      var grid = panel.querySelector(".menu-panel__grid");
      var empty = panel.querySelector(".menu-panel__empty");
      if (!grid || !empty) return;
      var hasProducts = grid.querySelector(".product-card") !== null;
      empty.hidden = hasProducts;
      grid.hidden = !hasProducts;
    }

    function loadPanelProducts(slug, panel) {
      var fetchSlug = MENU_FETCH_SLUG[slug] || slug;
      return fetch("/shop/" + fetchSlug + "/")
        .then(function (response) {
          if (!response.ok) throw new Error("load failed");
          return response.text();
        })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, "text/html");
          var sourcePanel = doc.querySelector('[data-menu-panel="' + slug + '"]');
          if (!sourcePanel) return;
          var grid = panel.querySelector(".menu-panel__grid");
          var sourceGrid = sourcePanel.querySelector(".menu-panel__grid");
          if (grid && sourceGrid && sourceGrid.children.length) {
            grid.innerHTML = sourceGrid.innerHTML;
            panel.dataset.loaded = "true";
          }
          updatePanelEmpty(panel);
        })
        .catch(function () {
          updatePanelEmpty(panel);
        });
    }

    function setActive(slug, skipLazyLoad) {
      if (MENU_SLUGS.indexOf(slug) === -1) return;

      tabs.forEach(function (tab) {
        var isActive = tab.dataset.category === slug;
        tab.classList.toggle("is-active", isActive);
        tab.setAttribute("aria-selected", isActive ? "true" : "false");
      });

      panels.forEach(function (panel) {
        var isActive = panel.dataset.menuPanel === slug;
        if (isActive) {
          panel.hidden = false;
          panel.classList.add("is-active");
          requestAnimationFrame(function () {
            panel.classList.add("is-visible");
          });
          updatePanelEmpty(panel);
          if (!skipLazyLoad && panel.dataset.loaded !== "true" && !panel.querySelector(".product-card")) {
            loadPanelProducts(slug, panel);
          }
        } else {
          panel.classList.remove("is-visible", "is-active");
          panel.hidden = true;
        }
      });

      if (window.history.replaceState) {
        window.history.replaceState(null, "", window.location.pathname + window.location.search + "#" + slug);
      }
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        setActive(tab.dataset.category);
      });
    });

    panels.forEach(function (panel) {
      if (panel.querySelector(".product-card")) {
        panel.dataset.loaded = "true";
      }
      updatePanelEmpty(panel);
    });

    setActive(initialSlug, true);

    window.addEventListener("hashchange", function () {
      var slug = window.location.hash.replace("#", "");
      if (MENU_SLUGS.indexOf(slug) !== -1) {
        setActive(slug);
      }
    });
  }

  function initCheckoutWizard() {
    var flow = document.getElementById("checkout-flow");
    if (!flow) return;

    var form = document.getElementById("checkout-form");
    var panels = flow.querySelectorAll("[data-checkout-step]");
    var progressSteps = document.querySelectorAll(".checkout-progress__step");
    var backBtn = document.getElementById("checkout-back");
    var nextBtn = document.getElementById("checkout-next");
    var stepNav = document.getElementById("checkout-step-nav");
    var firstName = document.getElementById("id_first_name");
    var lastName = document.getElementById("id_last_name");
    var pickupNote = document.getElementById("id_pickup_note");
    var notesField = document.getElementById("id_notes");
    var country = document.getElementById("id_country");
    var submitBtn = document.getElementById("checkout-submit");

    var minStep = 1;
    var maxStep = 3;
    var initialStep = parseInt(flow.getAttribute("data-initial-step"), 10) || minStep;
    var currentStep = initialStep;
    var mobileNext = document.getElementById("checkout-mobile-next");

    var paymentLabels = {
      online: "پرداخت آنلاین",
      counter_card: "پرداخت با کارت در صندوق",
      cash: "پرداخت نقدی در صندوق",
    };

    if (country && !country.value) {
      country.value = "Iran";
    }

    if (backBtn) {
      backBtn.setAttribute("data-href", "/cart/");
    }

    function syncHiddenFields() {
      if (firstName && lastName) {
        lastName.value = (firstName.value || "").trim() || firstName.value;
      }
      if (pickupNote && notesField) {
        notesField.value = (pickupNote.value || "").trim();
      }
    }

    function getField(id) {
      return document.getElementById(id);
    }

    var phoneField = getField("id_phone");
    if (phoneField) {
      phoneField.setAttribute("required", "required");
      phoneField.setAttribute("autocomplete", "tel");
    }
    if (firstName) {
      firstName.setAttribute("required", "required");
      firstName.setAttribute("autocomplete", "given-name");
    }

    function selectedPaymentMethod() {
      var selected = flow.querySelector('input[name="payment_method"]:checked');
      return selected ? selected.value : "online";
    }

    function validateStep(step) {
      if (step === 1) {
        syncHiddenFields();
        var required = [firstName, getField("id_phone")];
        for (var i = 0; i < required.length; i++) {
          if (!required[i] || !required[i].value.trim()) {
            if (required[i]) required[i].focus();
            return false;
          }
        }
        return true;
      }
      if (step === 2) {
        return !!flow.querySelector('input[name="payment_method"]:checked');
      }
      return true;
    }

    function updateReview() {
      syncHiddenFields();
      var nameEl = document.getElementById("review-name");
      var phoneEl = document.getElementById("review-phone");
      var emailEl = document.getElementById("review-email");
      var noteEl = document.getElementById("review-note");
      var paymentEl = document.getElementById("review-payment");

      if (nameEl && firstName) nameEl.textContent = firstName.value.trim() || "—";
      if (phoneEl) {
        var phone = getField("id_phone");
        phoneEl.textContent = phone && phone.value.trim() ? phone.value.trim() : "—";
      }
      if (emailEl) {
        var email = getField("id_email");
        emailEl.textContent = email && email.value.trim() ? email.value.trim() : "—";
      }
      if (noteEl && pickupNote) {
        noteEl.textContent = pickupNote.value.trim() ? pickupNote.value.trim() : "—";
      }
      if (paymentEl) {
        paymentEl.textContent = paymentLabels[selectedPaymentMethod()] || "—";
      }
      if (submitBtn) {
        submitBtn.textContent =
          selectedPaymentMethod() === "online"
            ? "پرداخت آنلاین و ثبت سفارش"
            : "ثبت سفارش";
      }
    }

    function updateProgress(step) {
      progressSteps.forEach(function (el, index) {
        var stepNum = index + 1;
        el.classList.toggle("is-active", stepNum === step);
        el.classList.toggle("is-complete", stepNum < step);
      });
    }

    function showStep(step) {
      currentStep = step;
      panels.forEach(function (panel) {
        var panelStep = parseInt(panel.getAttribute("data-checkout-step"), 10);
        var isActive = panelStep === step;
        if (isActive) {
          panel.hidden = false;
          panel.classList.add("is-active");
          requestAnimationFrame(function () {
            panel.classList.add("is-visible");
          });
        } else {
          panel.classList.remove("is-visible", "is-active");
          panel.hidden = true;
        }
      });

      updateProgress(step);

      if (backBtn) {
        backBtn.hidden = false;
        backBtn.textContent = step <= minStep ? "بازگشت به سبد" : "بازگشت";
      }
      if (nextBtn) {
        nextBtn.hidden = step >= maxStep;
        nextBtn.textContent = step === maxStep - 1 ? "بررسی" : "ادامه";
      }
      if (stepNav) {
        stepNav.hidden = step >= maxStep;
      }

      if (step === maxStep) {
        updateReview();
      }

      if (mobileNext) {
        if (step >= maxStep) {
          mobileNext.hidden = true;
        } else {
          mobileNext.hidden = false;
          mobileNext.textContent = step === maxStep - 1 ? "بررسی" : "ادامه";
        }
      }

      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    if (mobileNext && nextBtn) {
      mobileNext.addEventListener("click", function () {
        if (currentStep >= maxStep) return;
        nextBtn.click();
      });
    }

    if (backBtn) {
      backBtn.addEventListener("click", function () {
        if (currentStep > minStep) {
          showStep(currentStep - 1);
        } else {
          window.location.href = backBtn.getAttribute("data-href") || "/cart/";
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        if (!validateStep(currentStep)) return;
        if (currentStep < maxStep) {
          showStep(currentStep + 1);
        }
      });
    }

    if (form) {
      form.addEventListener("submit", function (e) {
        syncHiddenFields();
        if (!validateStep(1) || !validateStep(2)) {
          e.preventDefault();
          if (!validateStep(1)) {
            showStep(1);
          } else {
            showStep(2);
          }
        }
      });
    }

    showStep(form && form.dataset.hasErrors ? 1 : currentStep);
  }

  function initCartQtyControls() {
    document.querySelectorAll(".cart-line__qty-form").forEach(function (qtyForm) {
      var input = qtyForm.querySelector(".qty-input");
      if (!input) return;

      qtyForm.querySelectorAll(".qty-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var current = parseInt(input.value, 10) || 0;
          var min = parseInt(input.min, 10) || 0;
          var max = parseInt(input.max, 10) || 99;

          if (btn.dataset.action === "increase" && current < max) {
            input.value = current + 1;
          } else if (btn.dataset.action === "decrease" && current > min) {
            input.value = current - 1;
          }
          qtyForm.requestSubmit();
        });
      });
    });
  }

  function boot() {
    initMenuDrawer();
    initHeaderNavActive();
    initHomePage();
    requestAnimationFrame(initPageMotion);
    initCafeMenu();
    initCheckoutWizard();
    initCartQtyControls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
