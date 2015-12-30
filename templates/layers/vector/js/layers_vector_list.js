var dataView;
var grid;
var checkboxSelector = new Slick.CheckboxSelectColumn({
  cssClass: "slick-cell-checkboxsel"
});
var columns = [ checkboxSelector.getColumnDefinition(),
  { id: "id", name: "ID", field: "id", resizable: false, width: 50, sortable: true, sorter: sorterNumeric,
      formatter: linkFormatter = function ( row, cell, value, columnDef, dataContext ) {
            return '<a href="javascript:void(0)" onclick="layerViewer('+dataContext['id']+')">' + value + '</a>';
      }
  },
  { id: "name", name: "Name", field: "name", resizable: true, width: 200, sortable: true, sorter: sorterStringCompare,
      formatter: linkFormatter = function ( row, cell, value, columnDef, dataContext ) {
            return '<a href="javascript:void(0)" onclick="layerViewer('+dataContext['id']+')">' + value + '</a>';
      }
  },
  { id: "maps", name: "Appears in maps", field: "maps", resizable: true, width: 200, sortable: true, sorter: sorterStringCompare, 
     formatter: mapsListDropDown = function ( row, cell, value, columnDef, dataContext ) {
            var dropDown = '';
            for (var i = 0; i < value.length; i++) { dropDown += '<option value="'+value[i].map_id+'">'+value[i].map_name+'</option>'};
            return '<select style="width:100%; background:transparent; position:absolute; border:0; top:0; left:0;">'+dropDown+'</select>';
     }
  },
  { id: "geom_type", name: "Geometry Type", field: "geom_type", resizable: true, width: 200, sortable: true, sorter: sorterStringCompare },
  { id: "date_created", name: "Date Created", field: "date_created", resizable: true, width: 200, sortable: true, sorter: sorterDateIso, formatter: dateTimeFormatter },
  { id: "date_updated", name: "Date Updated", field: "date_updated", resizable: true, width: 200, sortable: true, sorter: sorterDateIso, formatter: dateTimeFormatter },
  { id: "attributes", name: "Attributes", field: "Attribute", resizable: true, width: 200, sortable: false,
     formatter: linkFormatter = function ( row, cell, value, columnDef, dataContext ) {
            return '<a href="javascript:void(0)" onclick="attributesTable('+dataContext['id']+')">' + 'Attributes' + '</a>';
      }
  }
  ]

function dateTimeFormatter(row, cell, value, columnDef, dataContext) {
  var d = new Date(Date.parse(value));
  return d.toUTCString();
}
var columnFilters = {};

var options = {
  enableCellNavigation: true,
  enableColumnReorder: false,
  multiColumnSort: true,
  showHeaderRow: true,
  headerRowHeight: 29,
  forceFitColumns: true,
  explicitInitialization: true,
};

function sorterStringCompare(a, b) {
  var x = a[sortcol], y = b[sortcol];
  return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
}

function sorterNumeric(a, b) {
  var x = (isNaN(a[sortcol]) || a[sortcol] === "" || a[sortcol] === null) ? -99e+10 : parseFloat(a[sortcol]);
  var y = (isNaN(b[sortcol]) || b[sortcol] === "" || b[sortcol] === null) ? -99e+10 : parseFloat(b[sortcol]);
  return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
}

function sorterRating(a, b) {
  var xrow = a[sortcol], yrow = b[sortcol];
  var x = xrow[3], y = yrow[3];
  return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
}

function sorterDateIso(a, b) {
  var regex_a = new RegExp("^((19[1-9][1-9])|([2][01][0-9]))\\d-([0]\\d|[1][0-2])-([0-2]\\d|[3][0-1])(\\s([0]\\d|[1][0-2])(\\:[0-5]\\d){1,2}(\\:[0-5]\\d){1,2})?$", "gi");
  var regex_b = new RegExp("^((19[1-9][1-9])|([2][01][0-9]))\\d-([0]\\d|[1][0-2])-([0-2]\\d|[3][0-1])(\\s([0]\\d|[1][0-2])(\\:[0-5]\\d){1,2}(\\:[0-5]\\d){1,2})?$", "gi");

  if (regex_a.test(a[sortcol]) && regex_b.test(b[sortcol])) {
    var date_a = new Date(a[sortcol]);
    var date_b = new Date(b[sortcol]);
    var diff = date_a.getTime() - date_b.getTime();
    return sortdir * (diff === 0 ? 0 : (date_a > date_b ? 1 : -1));
  }
  else {
    var x = a[sortcol], y = b[sortcol];
    return sortdir * (x === y ? 0 : (x > y ? 1 : -1));
  }
}

$(document).ready(function () {
  function filter(item) {
    for (var columnId in columnFilters) {
      if (columnId !== undefined && columnFilters[columnId] !== "") {
        var c = grid.getColumns()[grid.getColumnIndex(columnId)];
        if (item[c.field] != columnFilters[columnId]) {
          return false;
        }
      }
    }
    return true;
  }

  dataView = new Slick.Data.DataView();
  grid = new Slick.Grid(".dataGrid", dataView, columns, options);
  grid.setSelectionModel(new Slick.RowSelectionModel({selectActiveRow: false}));
  grid.registerPlugin(checkboxSelector);

  var columnpicker = new Slick.Controls.ColumnPicker(columns, grid, options);
;

  $(function () {

    dataView.onRowCountChanged.subscribe(function (e, args) {
      grid.updateRowCount();
      grid.render();
    });

    dataView.onRowsChanged.subscribe(function (e, args) {
      grid.invalidateRows(args.rows);
      grid.render();
    });


    $(grid.getHeaderRow()).delegate(":input", "change keyup", function (e) {
      var columnId = $(this).data("columnId");
      if (columnId != null) {
        columnFilters[columnId] = $.trim($(this).val());
        dataView.refresh();
      }
    });

    grid.onCellChange.subscribe(function (e, args) {
      updateAttributeTable(e, args);
    });

    grid.onHeaderRowCellRendered.subscribe(function(e, args) {
      $(args.node).empty();
      $("<input type='text'>")
        .data("columnId", args.column.id)
        .val(columnFilters[args.column.id])
        .appendTo(args.node);
    });

    grid.init();

    $.ajax({
          type: "GET",
          url: "/basqui/tree/layers/list/loader/{{ folder.pk }}/",
          success: function(r) {
                      dataView.beginUpdate();
                      dataView.setItems(r);
                      dataView.setFilter(filter);
                      dataView.endUpdate();
                    },
          error: function(xhr, ajaxOptions, thrownError) {
            alert(xhr.responseText);
          }
    });



  })

  grid.onColumnsResized.subscribe(function(e,args) {
    var columns = grid.getColumns();
    var columnsWidth = -2;
    for (var x in columns){
        columnsWidth += columns[x].width;
        console.log(columns[x]);
    };
    $(".grid-header").width(columnsWidth);
    $(".grid-footer").width(columnsWidth);
   });

  grid.onSort.subscribe(function (e, args) {
    var cols = args.sortCols;

    dataView.sort(function (dataRow1, dataRow2) {
      for (var i = 0, l = cols.length; i < l; i++) {
        sortdir = cols[i].sortAsc ? 1 : -1;
        sortcol = cols[i].sortCol.field;

        var result = cols[i].sortCol.sorter(dataRow1, dataRow2);
        if (result != 0) {
          return result;
          }
        }
        return 0;
      });
      args.grid.invalidateAllRows();
      args.grid.render();
  });
});