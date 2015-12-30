/* gettext library */

var catalog = new Array();

function pluralidx(count) { return (count == 1) ? 0 : 1; }


function gettext(msgid) {
  var value = catalog[msgid];
  if (typeof(value) == 'undefined') {
    return msgid;
  } else {
    return (typeof(value) == 'string') ? value : value[0];
  }
}

function ngettext(singular, plural, count) {
  value = catalog[singular];
  if (typeof(value) == 'undefined') {
    return (count == 1) ? singular : plural;
  } else {
    return value[pluralidx(count)];
  }
}

function gettext_noop(msgid) { return msgid; }

function pgettext(context, msgid) {
  var value = gettext(context + '' + msgid);
  if (value.indexOf('') != -1) {
    value = msgid;
  }
  return value;
}

function npgettext(context, singular, plural, count) {
  var value = ngettext(context + '' + singular, context + '' + plural, count);
  if (value.indexOf('') != -1) {
    value = ngettext(singular, plural, count);
  }
  return value;
}

function interpolate(fmt, obj, named) {
  if (named) {
    return fmt.replace(/%\(\w+\)s/g, function(match){return String(obj[match.slice(2,-2)])});
  } else {
    return fmt.replace(/%s/g, function(match){return String(obj.shift())});
  }
}

/* Collapse Function */
function fieldsetCollapse(module, key_id) {
    function show () { // Show
        $(this).text(gettext("Hide"))
            .closest("fieldset")
            .removeClass("collapsed")
            .addClass("open")
            .trigger("show.fieldset", [$(this).attr("id")]);
        window.localStorage.setItem($(this).attr("id"), true);
        $(this).one("click", hide);
    }
    function hide () { // Hide
        $(this).text(gettext("Show"))
        $(this).text(gettext("Show"))
            .closest("fieldset")
            .removeClass("open")
            .addClass("collapsed")
            .trigger("hide.fieldset", [$(this).attr("id")]);
        window.localStorage.removeItem($(this).attr("id"))
        $(this).one("click", show);
        return false;
    }
    // Add anchor tag for Show/Hide link
    $("fieldset.collapse:not(.open, .collapsed)").each(function (i, elem) {
        // Don't hide if fields in this fieldset have errors
        var key = module + '_fieldsetcollapser_' + i + '_' + key_id;
        if (typeof (window.localStorage) != 'undefined') {
            var item = $(elem)
            .addClass("collapsed")
            .find("h2")
            .first()
            .append(' (<a id=' +
                    key +
                    ' " class="collapse-toggle" href="#">' +
                    gettext("Show") +
                    '</a>)'
            ).find('a');
            if (window.localStorage.getItem(key)) {
                show.apply(item);
                $(item).one("click", hide);
            }else {
              if ($("ul.errorlist").length >0) {
                  show.apply(item);
                  $(item).one("click", hide);
              }else{
                 $(item).one("click", show);
            }
            }

        } else {
            throw "window.localStorage, not defined";
        }
    });
}
