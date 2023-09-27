"use strict";

function talkButton() {
  const btn = document.getElementById("talkBtn");
  const target = document.getElementById("popOut");
  const mail =
    "https://gokagn.com/wp-content/themes/theme_gokagn-official/assets/images/common/icon_contact-mail.png";
  let num = 0;
  let count = 0;
  let max = 19;
  let min = 1;

  function addImg() {
    num = Math.floor(Math.random() * (max - min) + min);
    count += 1;
    const img =
      '<img src="' +
      mail +
      '" class="c-popMail c-popMail-' +
      num +
      " jsMail-" +
      count +
      '" alt="">';
    target.insertAdjacentHTML("afterbegin", img);

    const removeElem = ".jsMail-" + count;
    const removeImg = document.querySelector(removeElem);

    setTimeout(() => {
      removeImg.remove();
    }, 3000);
  }

  btn.addEventListener("mouseover", () => {
    addImg();
  });
}
talkButton();

// scroll
function scrollMoving() {
  gsap.registerPlugin(ScrollTrigger);

  var fadeIn = document.querySelectorAll(".jsFadeIn");
  for (var i = fadeIn.length - 1; i >= 0; i--) {
    gsap.set(fadeIn[i], {
      opacity: 0,
    });
    gsap.to(fadeIn[i], {
      scrollTrigger: {
        trigger: fadeIn[i],
        start: "top 95%",
        end: "top top",
        toggleActions: "play none none none",
      },
      opacity: 1,
      duration: 0.8,
    });
  }

  var fadeUp = document.querySelectorAll(".jsFadeUp");
  for (var i = fadeUp.length - 1; i >= 0; i--) {
    if (window.innerWidth < 836) {
      gsap.set(fadeUp[i], {
        opacity: 0,
        y: 80,
      });
    } else {
      gsap.set(fadeUp[i], {
        opacity: 0,
        y: 150,
      });
    }
    gsap.to(fadeUp[i], {
      scrollTrigger: {
        trigger: fadeUp[i],
        start: "top 100%",
        end: "top top",
        toggleActions: "play none none none",
      },
      y: 0,
      opacity: 1,
      duration: 0.5,
    });
  }

  var fadeUp = document.querySelectorAll(".jsFadeUpTopImg");
  for (var i = fadeUp.length - 1; i >= 0; i--) {
    if (window.innerWidth < 836) {
      gsap.set(fadeUp[i], {
        opacity: 0,
        y: 50,
      });
    } else {
      gsap.set(fadeUp[i], {
        opacity: 0,
        y: 150,
      });
    }
    gsap.to(fadeUp[i], {
      scrollTrigger: {
        trigger: fadeUp[i],
        start: "top 110%",
        end: "top top",
        toggleActions: "play none none none",
      },
      y: 0,
      opacity: 1,
      duration: 0.5,
    });
  }

  var fadeUpContent = document.querySelectorAll(".jsFadeUpContent");
  for (var i = fadeUpContent.length - 1; i >= 0; i--) {
    gsap.set(fadeUpContent[i], {
      opacity: 0,
      y: 20,
    });
    gsap.to(fadeUpContent[i], {
      scrollTrigger: {
        trigger: fadeUpContent[i],
        start: "top 100%",
        end: "top top",
        toggleActions: "play none none none",
      },
      y: 0,
      opacity: 1,
      duration: 1,
    });
  }

  var fadeUp = document.querySelectorAll(".jsFadeUpSlow");
  for (var i = fadeUp.length - 1; i >= 0; i--) {
    if (window.innerWidth < 836) {
      gsap.set(fadeUp[i], {
        opacity: 0,
        y: 80,
      });
    } else {
      gsap.set(fadeUp[i], {
        opacity: 0,
        y: 150,
      });
    }
    gsap.to(fadeUp[i], {
      scrollTrigger: {
        trigger: fadeUp[i],
        start: "top 100%",
        end: "top top",
        toggleActions: "play none none none",
      },
      y: 0,
      opacity: 1,
      duration: 1,
    });
  }

  var fadeUp = document.querySelectorAll(".jsFadeInright");
  for (var i = fadeUp.length - 1; i >= 0; i--) {
    if (window.innerWidth < 836) {
      gsap.set(fadeUp[i], {
        opacity: 0,
        x: 50,
      });
    } else {
      gsap.set(fadeUp[i], {
        opacity: 0,
        x: 200,
      });
    }
    gsap.to(fadeUp[i], {
      scrollTrigger: {
        trigger: fadeUp[i],
        start: "top 100%",
        end: "top top",
        toggleActions: "play none none none",
      },
      x: 0,
      opacity: 1,
      duration: 1,
    });
  }

  var scrollShow = document.querySelectorAll(".jsScrollShow");
  for (var i = scrollShow.length - 1; i >= 0; i--) {
    ScrollTrigger.create({
      trigger: scrollShow[i],
      start: "top 98%",
      end: "top top",
      toggleClass: { targets: scrollShow[i], className: "is-animated" },
      once: true,
    });
  }

  var scrollShow = document.querySelectorAll(".jsScrollShowAbout");
  for (var i = scrollShow.length - 1; i >= 0; i--) {
    ScrollTrigger.create({
      trigger: scrollShow[i],
      start: "top 93%",
      end: "top top",
      toggleClass: { targets: scrollShow[i], className: "is-animated" },
      once: true,
    });
  }

  var paScrollShow = document.querySelectorAll(".jsPAScrollShow");
  for (var i = paScrollShow.length - 1; i >= 0; i--) {
    ScrollTrigger.create({
      trigger: paScrollShow[i],
      start: "top 100%",
      end: "top top",
      toggleClass: { targets: paScrollShow[i], className: "is-animated" },
      once: true,
    });
  }

  var paScrollShowText = document.querySelectorAll(".jsPAScrollShowText");
  for (var i = paScrollShowText.length - 1; i >= 0; i--) {
    ScrollTrigger.create({
      trigger: paScrollShowText[i],
      start: "top 115%",
      end: "top top",
      toggleClass: { targets: paScrollShowText[i], className: "is-animated" },
      once: true,
    });
  }

  var footerShow = document.querySelectorAll(".jsFooterShow");
  for (var i = footerShow.length - 1; i >= 0; i--) {
    ScrollTrigger.create({
      trigger: footerShow[i],
      start: "top 95%",
      end: "top top",
      toggleClass: { targets: footerShow[i], className: "is-animated" },
      once: true,
    });
  }
}
scrollMoving();
