"use strict";

const root = "https://localhost:10162";

// page heading h1
function pageTitle() {
  let target = document.getElementById("pageTitle");
  setTimeout(() => {
    target.classList.add("is-animation");
  }, 300);
}

// menu open
function navOpen() {
  let btn = document.getElementById("navBtn"),
    nav = document.getElementById("nav");

  btn.addEventListener("click", () => {
    nav.classList.toggle("is-open");
    btn.classList.toggle("is-open");
  });
}
navOpen();

// header logo hover
VanillaTilt.init(document.querySelector("#headerLogo"), {
  max: 45,
  speed: 800,
  scale: 1.4,
  reverse: true,
  perspective: 1000,
});



// page tranfar
jQuery(function ($) {
  $(function () {
    window.onpageshow = function (event) {
      if (event.persisted) {
        window.location.reload();
      }
    };
    $("a:not([target])").on("click", function (e) {
      e.preventDefault();
      var url = $(this).attr("href");
      if (url !== "") {
        $("#transfar").addClass("is-transfar");
        setTimeout(function () {
          window.location = url;
        }, 1500);
      }
      return false;
    });
  });
});

// smoothscroll
var urlHash = location.hash;
if (urlHash) {
  $("body,html").stop().scrollTop(0);
  setTimeout(function () {
    var target = $(urlHash);
    var position = target.offset().top - 50;
    $("body,html").stop().animate({ scrollTop: position }, 400);
  });
}
$('a[href^="#"]').click(function () {
  var href = $(this).attr("href");
  var target = $(href);
  var position = target.offset().top - 50;
  $("body,html").stop().animate({ scrollTop: position }, 400);
});

// projects cursor
function cursor() {
  const cursor = document.getElementById("cursor");

  document.addEventListener("mousemove", function (e) {
    cursor.style.transform =
      "translate(" + e.clientX + "px, " + e.clientY + "px)";
  });

  const setAction = document.querySelectorAll(".jsFollowerContainer");
  for (let i = 0; i < setAction.length; i++) {
    setAction[i].addEventListener("mouseover", function (e) {
      cursor.classList.add("is-hover");
    });
    setAction[i].addEventListener("mouseout", function (e) {
      cursor.classList.remove("is-hover");
    });
  }
}
