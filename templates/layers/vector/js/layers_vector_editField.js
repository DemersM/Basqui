$('select').on('change', function() {
  row_id = this.id.substring(8,9);
  if (this.value == 0 ){
    $("input[id='id_form-"+row_id+"-width']").val(11);
    $("input[id='id_form-"+row_id+"-precision']").val(0);
    $("input[id='id_form-"+row_id+"-width']").prop('readonly', false);
    $("input[id='id_form-"+row_id+"-precision']").prop('readonly', true);
  }else if (this.value == 2){
    $("input[id='id_form-"+row_id+"-width']").val(10);
    $("input[id='id_form-"+row_id+"-precision']").val(4);
    $("input[id='id_form-"+row_id+"-width']").prop('readonly', false);
    $("input[id='id_form-"+row_id+"-precision']").prop('readonly', false);
  }else if (this.value == 4){
    $("input[id='id_form-"+row_id+"-width']").val(24);
    $("input[id='id_form-"+row_id+"-precision']").val(0);
    $("input[id='id_form-"+row_id+"-width']").prop('readonly', false);
    $("input[id='id_form-"+row_id+"-precision']").prop('readonly', true);
  }else{
    $("input[id='id_form-"+row_id+"-width']").val(0);
    $("input[id='id_form-"+row_id+"-precision']").val(0);
    $("input[id='id_form-"+row_id+"-width']").prop('readonly', true);
    $("input[id='id_form-"+row_id+"-precision']").prop('readonly', true);
  }
})

function updateElementIndex(el, prefix, ndx) {
  var id_regex = new RegExp('(' + prefix + '-\\d+)');
  var replacement = prefix + '-' + ndx;
  if ($(el).attr("for")) { $(el).attr("for", $(el).attr("for").replace(id_regex, replacement));}
  if (el.id) el.id = el.id.replace(id_regex, replacement);
  if (el.name) el.name = el.name.replace(id_regex, replacement);
}

function addForm(btn, prefix) {
  var formCount = parseInt($('#id_' + prefix + '-TOTAL_FORMS').val());
  var row = $('.dynamic-form:last').clone(true).get(0);
  console.log(row)
  $(row).insertAfter($('.dynamic-form:last')).children('.hidden').removeClass('hidden');
  $(row).children().not(':last').children().children().each(function() {
    updateElementIndex(this, prefix, formCount);
    $(this).removeAttr("readonly");
    if ($(this).attr('name') === prefix+'-'+formCount+'-width' || $(this).attr('name') === prefix+'-'+formCount+'-precision') {
      $(this).val(0);
    } else {
      $(this).val('');
    }
  });
  $('#id_' + prefix + '-TOTAL_FORMS').val(formCount + 1);
  return false;
}

$('.add-row').click(function() {
  return addForm(this, 'form');
});