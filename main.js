(function () {
  'use strict';

  var root = document.documentElement;

  var META = {
    it: {
      title: 'Raul Osifo · Automazioni e integrazioni per l’e-commerce',
      description: 'Portfolio di Raul Osifo, Automation & Integrations Specialist a Torino. Caso studio: l’automazione di Spirit Ink, dall’ordine pagato su Shopify alla spedizione.'
    },
    en: {
      title: 'Raul Osifo · Automation and integrations for e-commerce',
      description: 'Portfolio of Raul Osifo, Automation & Integrations Specialist based in Turin. Case study: Spirit Ink’s automation, from a paid Shopify order to delivery.'
    }
  };

  function each(selector, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(selector), fn);
  }

  // Text swaps through CSS (html[lang]); attributes that CSS can't reach are swapped here.
  function apply(lang) {
    root.lang = lang;
    document.title = META[lang].title;

    var description = document.querySelector('meta[name="description"]');
    if (description) description.setAttribute('content', META[lang].description);

    each('[data-set-lang]', function (button) {
      button.setAttribute('aria-pressed', String(button.getAttribute('data-set-lang') === lang));
    });
    each('[data-alt-' + lang + ']', function (el) {
      el.setAttribute('alt', el.getAttribute('data-alt-' + lang));
    });
    each('[data-aria-' + lang + ']', function (el) {
      el.setAttribute('aria-label', el.getAttribute('data-aria-' + lang));
    });
    each('[data-href-' + lang + ']', function (el) {
      el.setAttribute('href', el.getAttribute('data-href-' + lang));
    });
  }

  function choose(lang) {
    apply(lang);
    try { localStorage.setItem('lang', lang); } catch (e) {}
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('lang', lang);
      window.history.replaceState(null, '', url);
    } catch (e) {}
  }

  apply(root.lang === 'en' ? 'en' : 'it');

  each('[data-set-lang]', function (button) {
    button.addEventListener('click', function () {
      choose(button.getAttribute('data-set-lang'));
    });
  });

  // Hairline under the masthead once the page has moved.
  var masthead = document.getElementById('masthead');
  if (masthead) {
    var onScroll = function () {
      masthead.classList.toggle('is-scrolled', window.scrollY > 8);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }
})();
