$(document).ready(function () {
    var p1offset;
    var p2offset;
    var p3offset;
    var p4offsets;
    let scrollmax2;
    $("#InputLoader").hide();

    //$("body").css("overflow", "hidden");
    $(window).scroll(function () {
        var height = $(window).scrollTop();

        if (
            height > $("#PAGE02").offset().top + 300 &&
            height < $("#PAGE03").offset().top - 200
        ) {
            $(".header").css("color", "#0e1f33");
        } else {
            $(".header").css("color", "#0e1f33");
        }
    });
    $(".owl-carousel").owlCarousel({
        transitionStyle: "bounce",
        loop: false,
        nav: true,
        mouseDrag: false,
        touchDrag: false,
        dots: false,
        slideBy: 3,
        navText: ['<div class="prevArrow" />', '<div class="nextArrow" />'],
        responsive: {
            0: {
                items: 1,
            },
            1040: {
                items: 2,
            },
            1400: {
                items: 3,
            },
        },
    });
    var preloadIconParams = {
        container: document.getElementById("preloaderIcon"),
        renderer: "svg",
        loop: true,
        autoplay: true,
        // path: "static/assets/PAGE00/pg0_loadingLoop.json", // the path to the animation json
    };

    var pg1_Lottie_SquiggleParams = {
        container: document.getElementById("pg1_Lottie_Squiggle"),
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: "static/assets/PAGE01/pg1_waveStrokeTop/pg1_waveStrokeTop.json", // the path to the animation json
    };
    var pg1_Lottie_SquiggleBottomParams = {
        container: document.getElementById("pg1_Lottie_SquiggleBottom"),
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: "static/assets/PAGE01/pg1_waveStrokeBottom/pg1_waveStrokeBottom.json", // the path to the animation json
    };
    var pg3_Lottie_SquiggleTopParams = {
        container: document.getElementById("pg3_Lottie_SquiggleTop"),
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: "static/assets/PAGE02/pg2_waveStrokeBottom.json", // the path to the animation json
    };

    var pg3_Lottie_SquiggleBottomParams = {
        container: document.getElementById("pg3_Lottie_SquiggleBottom"),
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: "static/assets/PAGE03/pg3_strokeWaveBottom.json", // the path to the animation json
    };

    var preloadIcon;
    var anim;
    var anim2;
    var anim3;
    var anim4;

    anim = lottie.loadAnimation(preloadIconParams);
    anim = lottie.loadAnimation(pg1_Lottie_SquiggleParams);
    anim2 = lottie.loadAnimation(pg1_Lottie_SquiggleBottomParams);
    anim3 = lottie.loadAnimation(pg3_Lottie_SquiggleTopParams);
    anim4 = lottie.loadAnimation(pg3_Lottie_SquiggleBottomParams);
    var $sections = $(".scrollBreak");

    $(window).on("load", function () {
        p1offset = $("#pageBreak1").offset().top;
        p2offset = $("#pageBreak2").offset().top;
        p3offset = $("#pageBreak3").offset().top;
        p4offset = $("#pageBreak4").offset().top;
        scrollmax2 = $(".pg2StepsSection").offset().top - 900;
        $sections = $(".scrollBreak");
        $("#preLoader").delay(100).fadeOut("slow");
        $(".heroTitle").addClass("animate");
        $(".heroSubTitle").addClass("animate");
        $(".pg1_mountainLeft").addClass("animate");
        $(".pg1_sun").addClass("animate");
        //$('.pg1_sun').addClass('animate');
        $(".mobileWrapper").addClass("animate");
        //$("body").css("overflow", "initial");
        $("#myVideo").trigger("play");
        /*setTimeout(function(){
          $("#preLoader").hide();
          $('html, body').animate({
            scrollTop: 1080
          }, 1000);
          $("body").css("overflow", "initial");
          $("#myVideo").css("width", "105%");
          $("body").css("overflow", "initial");
        },4000);*/
    });

    $(window).on("beforeunload", function () {
        $(window).scrollTop(0);
        $("body").css("overflow", "hidden");
        $("#preLoader").delay(100).fadeIn("fast");
        $("#preLoader").show();
    });

    // Function to reveal lightbox and adding YouTube autoplay
    function revealVideo(div, video_id) {
        var video = document.getElementById(video_id).src;
        document.getElementById(video_id).src = video + "&autoplay=1"; // adding autoplay to the URL
        document.getElementById(div).style.display = "block";
    }

    // Hiding the lightbox and removing YouTube autoplay
    function hideVideo(div, video_id) {
        var video = document.getElementById(video_id).src;
        var cleaned = video.replace("&autoplay=1", ""); // removing autoplay form url
        document.getElementById(video_id).src = cleaned;
        document.getElementById(div).style.display = "none";
    }

    $("#pg3_Card1_PlayButton").on("click", function () {
        revealVideo("video", "youtube");
    });
    $("#pg3_Card2_PlayButton").on("click", function () {
        revealVideo("video2", "youtube2");
    });
    $("#pg3_Card3_PlayButton").on("click", function () {
        revealVideo("video3", "youtube3");
    });
    $("#pg3_Card4_PlayButton").on("click", function () {
        revealVideo("video4", "youtube4");
    });
    $("#pg3_Card5_PlayButton").on("click", function () {
        revealVideo("video5", "youtube5");
    });

    $(".lightbox-close").on("click", function () {
        hideVideo("video", "youtube");
        hideVideo("video2", "youtube2");
        hideVideo("video3", "youtube3");
        hideVideo("video4", "youtube4");
        hideVideo("video5", "youtube5");
    });
    $(".lightbox").on("click", function () {
        hideVideo("video", "youtube");
        hideVideo("video2", "youtube2");
        hideVideo("video3", "youtube3");
        hideVideo("video4", "youtube4");
        hideVideo("video5", "youtube5");
    });

    var formSuccess =
        '<div class="messageSent"><div class="messageText"><h4>- Message sent -</h4><h1>Thank you!</h1><h3>We\'ll check in with you shortly</h3></div><div class="backgroundOverlay"></div></div>';

    $("#pg4_contactForm").on("submit", function (event) {
        event.preventDefault();
        var formData = $(this).serialize();
        $.ajax({
            type: "POST",
            url: "https://formspree.io/f/mzbqzpbz",
            dataType: "json",
            data: formData,
            success: function (response) {
                $("#InputLoader").html(formSuccess);
                $("#InputLoader").fadeIn("fast");
                setTimeout(function () {
                    $("#InputLoader").fadeOut("fast");
                }, 4000);
                var $nextSection = $($sections[0]);
                currentIndex = 0;
                var offsetTop = $nextSection.offset().top;
                isAnimating = true;
                moveUnderline(currentIndex);
                $("html, body").animate(
                    {scrollTop: offsetTop},
                    1000,
                    "easeInOutCubic",
                    stopAnimation
                );
            },
            error: function (xhr, status, error) {
                if ($("#formFirstName").val() === "") {
                    console.log("empty");
                    $("#formFirstName_error").addClass("active");
                } else {
                    $("#formFirstName_error").removeClass("active");
                }

                if ($("#formLastName").val() === "") {
                    console.log("empty last name");
                    $("#formLastName_error").addClass("active");
                } else {
                    $("#formLastName_error").removeClass("active");
                }
                if ($("#formEmail").val() === "") {
                    console.log("empty email");
                    $("#formEmail_error").addClass("active");
                } else {
                    $("#formEmail_error").removeClass("active");
                }
                if ($("#formSubject").val() === "") {
                    console.log("empty");
                    $("#subject_error").addClass("active");
                } else {
                    $("#subject_error").removeClass("active");
                }
                if ($("#formMessage").val() === "") {
                    console.log("empty message");
                    $("#formMessage_error").addClass("active");
                } else {
                    $("#formMessage_error").removeClass("active");
                }

                //  console.log(status);
            },
        });
    });

    let scrollheight = $(window).scrollTop();
    let document_height = $(document).height() - $(window).height();
    // Collecting the sections

    let scrollpercentage;
    let scrollpercentage2;

    let percentageGap = 82;
    let percentageGap2 = 350;
    let videoOffset;
    var pg1_mountainLeft_top;
    var pg4_mountainLeft_top_Offset;
    var pg1_sun_top;
    $(window).scroll(function () {
        scrollheight = window.pageYOffset;

        if (scrollheight > scrollmax2) {
            $(".titleStepCol").addClass("inView");
        }
        if (scrollheight < scrollmax2) {
            scrollpercentage = (100 / scrollmax2) * scrollheight;
            videoOffset = percentageGap * (scrollpercentage * 0.01);
            $("#myVideo").css({width: 187 - videoOffset + "%"});
        }

        switch (true) {
            case scrollheight > p3offset:
                $("#pg4_mountainFront").addClass("visible");
                $(".pg4_mountainBack").addClass("visible");
                $(".pg4_miniSun").addClass("visible");
                //currentIndex = 3;
                break;
            case scrollheight > p3offset - 100:
                $(".outroColumn").addClass("active");
                $(".formColumn").addClass("active");
                $("#styleColumn").addClass("active");
                $("#serviceColumns").addClass("active");
                $("#styleColumn").addClass("active");
                $("#serviceColumns").addClass("active");
                //currentIndex = 2;
                break;
            case scrollheight > p2offset - 100:
                pg1_mountainLeft_top = scrollheight / 20;
                pg1_sun_top = scrollheight / 60;
                $("#pg1_mountainLeft").css({
                    transform: "translate(0," + pg1_mountainLeft_top + "vh)",
                });
                $(".pg1_sun").css({transform: "translate(0," + pg1_sun_top + "vh)"});
                //currentIndex = 1;
                break;
            case scrollheight > p1offset - 100:
                pg1_mountainLeft_top = scrollheight / 20;
                pg1_sun_top = scrollheight / 60;
                $("#pg1_mountainLeft").css({
                    transform: "translate(0," + pg1_mountainLeft_top + "vh)",
                });
                $(".pg1_sun").css({transform: "translate(0," + pg1_sun_top + "vh)"});
                //currentIndex = 0;
                break;
        }
    });

    // Variable to hold the current section index
    var currentIndex = 0;

    // Variable to hold the animation state
    var isAnimating = false;

    // Define the animation finish callback
    var stopAnimation = function () {
        // We add the 300 ms timeout to debounce the mouse wheel event

        setTimeout(function () {
            // Set the animation state to false
            isAnimating = false;
        }, 300);
    };

    // Function returns true if DOM element bottom is reached
    var bottomIsReached = function ($elem) {
        var rect = $elem[0].getBoundingClientRect();
        return rect.bottom <= $(window).height();
    };

    // Function returns true if DOM element top is reached
    var topIsReached = function ($elem) {
        var rect = $elem[0].getBoundingClientRect();
        return rect.top >= 0;
    };

    function moveUnderline(index) {
        switch (index) {
            case 0:
                $("#navUnderline").css("left", "121px");
                $("#navUnderline").css("width", "61px");
                break;
            case 1:
                $("#navUnderline").css("left", "265px");
                $("#navUnderline").css("width", "64px");
                break;
            case 2:
                $("#navUnderline").css("left", "413px");
                $("#navUnderline").css("width", "82px");
                break;
            case 3:
                $("#navUnderline").css("left", "579px");
                $("#navUnderline").css("width", "79px");
                break;
        }
    }

    $(".PAGE01Link").on("click", function () {
        $("#menuToggle").prop("checked", false);
        var $nextSection = $($sections[0]);
        currentIndex = 0;
        var offsetTop = $nextSection.offset().top;
        isAnimating = true;
        moveUnderline(currentIndex);

        $("html, body").animate(
            {scrollTop: offsetTop},
            1000,
            "easeInOutCubic",
            stopAnimation
        );
    });
    $(".PAGE02Link").on("click", function () {
        $("#menuToggle").prop("checked", false);
        var $nextSection = $($sections[1]);
        currentIndex = 1;
        var offsetTop = $nextSection.offset().top;
        isAnimating = true;
        moveUnderline(currentIndex);
        $("html, body").animate(
            {scrollTop: offsetTop},
            1000,
            "easeInOutCubic",
            stopAnimation
        );
    });
    $(".PAGE03Link").on("click", function () {
        $("#menuToggle").prop("checked", false);
        if (currentIndex === 2) {
            $("#styleColumn").addClass("active");
            $("#serviceColumns").addClass("active");
        } else {
            $("#styleColumn").removeClass("active");
            $("#serviceColumns").removeClass("active");
        }
        var $nextSection = $($sections[2]);
        currentIndex = 2;
        var offsetTop = $nextSection.offset().top;
        isAnimating = true;
        moveUnderline(currentIndex);
        $("html, body").animate(
            {scrollTop: offsetTop},
            1000,
            "easeInOutCubic",
            stopAnimation
        );
    });
    $(".PAGE04Link").on("click", function () {
        $("#menuToggle").prop("checked", false);
        var $nextSection = $($sections[3]);
        currentIndex = 3;
        var offsetTop = $nextSection.offset().top;
        isAnimating = true;
        moveUnderline(currentIndex);
        if (currentIndex === 3) {
            $("#pg4_mountainFront").addClass("visible");
            $(".pg4_mountainBack").addClass("visible");
            $(".pg4_miniSun").addClass("visible");
            $(".outroColumn").addClass("active");
            $(".formColumn").addClass("active");
        } else {
            $("#pg4_mountainFront").removeClass("visible");
            $(".pg4_mountainBack").removeClass("visible");
            $(".pg4_miniSun").removeClass("visible");
            $(".outroColumn").removeClass("active");
            $(".formColumn").removeClass("active");
        }
        $("html, body").animate(
            {scrollTop: offsetTop},
            1000,
            "easeInOutCubic",
            stopAnimation
        );
    });
    $(".getInTouch").on("click", function () {
        var $nextSection = $($sections[3]);
        currentIndex = 3;
        var offsetTop = $nextSection.offset().top;
        isAnimating = true;
        $("#pg4_mountainFront").addClass("visible");
        $(".pg4_mountainBack").addClass("visible");
        $(".pg4_miniSun").addClass("visible");
        $(".outroColumn").addClass("active");
        $(".formColumn").addClass("active");
        moveUnderline(currentIndex);
        $("html, body").animate(
            {scrollTop: offsetTop},
            1000,
            "easeInOutCubic",
            stopAnimation
        );
    });
    document.addEventListener(
        "wheel",
        function (event) {
            if (isAnimating) {
                event.preventDefault();
                return;
            }
            var $currentSection = $($sections[currentIndex]);
            var direction = event.deltaY;
            if (direction > 0) {
                if (currentIndex + 1 >= $sections.length) return;
                currentIndex++;
                var $nextSection = $($sections[currentIndex]);
                var offsetTop = $nextSection.offset().top;
                event.preventDefault();
                isAnimating = true;
                moveUnderline(currentIndex);
                if (currentIndex === 2) {
                    $("#styleColumn").addClass("active");
                    $("#serviceColumns").addClass("active");
                } else {
                    $("#styleColumn").removeClass("active");
                    $("#serviceColumns").removeClass("active");
                }
                if (currentIndex === 3) {
                    $("#pg4_mountainFront").addClass("visible");
                    $(".pg4_mountainBack").addClass("visible");
                    $(".pg4_miniSun").addClass("visible");
                    $(".outroColumn").addClass("active");
                    $(".formColumn").addClass("active");
                } else {
                    $("#pg4_mountainFront").removeClass("visible");
                    $(".pg4_mountainBack").removeClass("visible");
                    $(".pg4_miniSun").removeClass("visible");
                    $(".outroColumn").removeClass("active");
                    $(".formColumn").removeClass("active");
                }
                $("html, body").animate(
                    {scrollTop: offsetTop},

                    1000,
                    "easeInOutCubic",
                    stopAnimation
                );
            } else {
                if (currentIndex - 1 < 0) return;
                currentIndex--;
                var $previousSection = $($sections[currentIndex]);
                var offsetTop = $previousSection.offset().top;
                event.preventDefault();
                isAnimating = true;
                moveUnderline(currentIndex);
                if (currentIndex === 2) {
                    $("#styleColumn").addClass("active");
                    $("#serviceColumns").addClass("active");
                } else {
                    $("#styleColumn").removeClass("active");
                    $("#serviceColumns").removeClass("active");
                }
                if (currentIndex === 3) {
                    $("#pg4_mountainFront").addClass("visible");
                    $(".pg4_mountainBack").addClass("visible");
                    $(".pg4_miniSun").addClass("visible");
                    $(".outroColumn").addClass("active");
                    $(".formColumn").addClass("active");
                } else {
                    $("#pg4_mountainFront").removeClass("visible");
                    $(".pg4_mountainBack").removeClass("visible");
                    $(".pg4_miniSun").removeClass("visible");
                    $(".outroColumn").removeClass("active");
                    $(".formColumn").removeClass("active");
                }
                $("html, body").animate(
                    {scrollTop: offsetTop},
                    1000,
                    "easeInOutCubic",
                    stopAnimation
                );
            }
        },
        {passive: false}
    );

    var dots = $(".cardDots");
    var moreText = $(".cardMore");
    var btn = $(".cardReadMore");
    var moreCard = $(".serviceCardExplainMore");

    if (window.innerWidth < 768) {
        btn.show();
        moreText.hide();
        moreCard.hide();
        dots.show();
        btn.innerHTML = "Read more";
    } else {
        btn.hide();
        moreText.show();
        moreCard.hide();
        dots.hide();
        btn.innerHTML = "Read less";
    }

    function reportWindowSize() {
        if (window.innerWidth < 768) {
            $(".cardReadMore").show();
            $(".cardMore").hide();
            $(".serviceCardExplainMore").hide();
            dots.show();
            btn.innerHTML = "Read more";
        } else {
            $(".cardReadMore").hide();
            $(".cardMore").show();
            $(".serviceCardExplainMore").hide();
            dots.hide();
            btn.innerHTML = "Read less";
        }
    }

    function ReadmoreFunction(infoCard) {
        var presentDots = infoCard.children(".cardDots");
        var presentBtn = infoCard.children(".cardReadMore");
        var presentMore = infoCard.children(".serviceCardExplainMore");
        if (presentMore.is(":hidden")) {
            presentDots.show();
            presentMore.show();
        } else {
            presentDots.hide();
            presentMore.hide();
        }
    }

    window.addEventListener("resize", reportWindowSize);
    $(".cardReadMore").on("click", function () {
        ReadmoreFunction($(this).parent().parent());
    });
    $(".cardReadLess").on("click", function () {
        ReadmoreFunction($(this).parent().parent().parent());
    });
});
