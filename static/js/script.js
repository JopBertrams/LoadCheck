var elements = [];

[].forEach.call(document.querySelectorAll('.scroll-to-link'), function (div) {
  div.onclick = function (e) {
    e.preventDefault();
    var target = this.dataset.target;
    document.getElementById(target).scrollIntoView({ behavior: 'smooth' });
    var elems = document.querySelectorAll('.content-menu ul li');
    [].forEach.call(elems, function (el) {});
    return false;
  };
});

function debounce(func) {
  var timer;
  return function (event) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(func, 100, event);
  };
}

function calculElements() {
  var totalHeight = 0;
  elements = [];
  [].forEach.call(
    document.querySelectorAll('.content-section'),
    function (div) {
      var section = {};
      section.id = div.id;
      totalHeight += div.offsetHeight;
      section.maxHeight = totalHeight - 25;
      elements.push(section);
    }
  );
}

calculElements();
window.onload = () => {
  calculElements();
};
window.addEventListener(
  'resize',
  debounce(function (e) {
    e.preventDefault();
    calculElements();
  })
);
window.addEventListener('scroll', function (e) {
  e.preventDefault();
});
