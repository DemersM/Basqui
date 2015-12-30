$(document).ready(function(){
	  $("#showMessageBoard").show();
	  $("#messageBoard").hide();
		$("#messageBoard").resizable({
		handles: 'n' });		
	  $("#hideMessageBoard").click(function(){
	    $("#messageBoard").hide();
	    $("#showMessageBoard").show();
	  });
	  $("#showMessageBoard").click(function(){
	    $("#messageBoard").show();
	    $("#showMessageBoard").hide();
	  });
});

