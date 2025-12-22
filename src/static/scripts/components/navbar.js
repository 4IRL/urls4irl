"use strict";

const NAVBAR_TOGGLER = { toggler: null };

$(document).ready(function () {
  $("button#toMembers").on("click", () => {
    setMobileUIWhenMemberDeckSelected();
  });
  $("button#toURLs").on("click", () => {
    setMobileUIWhenUTubSelectedOrURLNavSelected();
  });
  $("button#toUTubs").on("click", () => {
    setMobileUIWhenUTubDeckSelected();
  });

  $("button#toTags").on("click", () => {
    setMobileUIWhenTagDeckSelected();
  });

  // Grab toggler for the navbar
  NAVBAR_TOGGLER.toggler = new bootstrap.Collapse("#NavbarNavDropdown", {
    toggle: false,
  });

  // Event listeners when hiding and showing the mobile navbar
  $("#NavbarNavDropdown")
    .on("show.bs.collapse", () => {
      onMobileNavbarOpened();
    })
    .on("hide.bs.collapse", () => {
      onMobileNavbarClosed();
    });
});

function onMobileNavbarOpened() {
  const navbarBackdrop = $(document.createElement("div")).addClass(
    "navbar-backdrop",
  );

  navbarBackdrop.on("click", function () {
    NAVBAR_TOGGLER.toggler.hide();
  });

  setTimeout(function () {
    navbarBackdrop.addClass("navbar-backdrop-show");
  }, 0);

  $(".navbar-brand").addClass("z9999");
  $(".navbar-toggler").addClass("z9999");
  $("#NavbarNavDropdown").addClass("z9999");

  $("#mainNavbar").append(navbarBackdrop);
}

function onMobileNavbarClosed() {
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}
