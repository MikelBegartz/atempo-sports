var $j = jQuery.noConflict();
$j(document).ready(function() {
	

	
	if ($j('#site_lang').length) {
		var site_lang = $j('#site_lang').val();
	} else {
		var site_lang = 'es';
	}
	
	var ruta_files = 'https://www.server2.sidgad.es/';
	var temp = $j('#temp').val();
	var cliente = $j('#cliente').val();
	var idm = $j('#idm').val();
	$j('.loading_portal').hide();
	var name_temp_selected = $j('#temp_activa_name').val();
	$j('#header_temp_selected').html(name_temp_selected+'<i class="fa fa-sort" aria-hidden="true" style="padding-left: 10px; font-size: 14px;"></i>');
	
	
	var idc = $j('#idc').val();
	
	
	

		/*
		if (idc>0) {
			$j('#tab_modal_contenido').hide();
			$j('#tab_modal_container').show();
			$j('#listado_competiciones').load(ruta_files+cliente+'/'+cliente+'_ls_'+idm+'.php',
				function( response, status, xhr ) {
					if (status == 'success') {
						//$j('.loading_portal').hide();
						//$j('.temp_'+temp).show();
						$j('#tabs_options').hide();
						$j('#'+idc).click();
					}
				}	
			);	
		} else {
		*/	
		
		
			
			$j('#listado_competiciones').load(ruta_files+cliente+'/'+cliente+'_ls_'+idm+'.php',
				function( response, status, xhr ) {
					if (status == 'success') {
						$j('.loading_portal').hide();
						$j('.temp_'+temp).show();
					
						var idc = $j('#idc').val();
						if (idc>0) {
							$j('#'+idc).click();
						}

				
						var id_custom_club = $j("#id_custom_club").val();
						if (id_custom_club>0) {
	
							console.log("hoiooooa");
							$j(".listado_competiciones_fila").hide();
							$j(".club_"+id_custom_club+ ".temp_"+temp).show();
							
						}	

					
					}
				}	
			);
			
			
					


if (cliente!='cerilh') {
	if (cliente=='worldskate') {
		$j('#scorer_competiciones').load(ruta_files+cliente+'/'+cliente+'_mc_'+idm+'_horizontal.php');
	}
} else {

	/*$j('#tab_modal_contenido_competicion').load(ruta_files+'/cerilh/overview.php',
		{

		},
		function( response, status, xhr ) {
			if (status == 'success') {
	
				$j('.loading_portal').hide();

				
			}
		}
	);	
	*/	var idc = $j('#idc').val();
		var idm = $j('#idm').val();
		var file = cliente+"_cal_2_"+temp+".php";
		$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+file,
			{
				idc: 			idc,
				tipo_stats: 	"",
				lang:			site_lang
			},
			function( response, status, xhr ) {
				if (status == 'success') {
					
					var team_id = $j('#input_team_selected').val();
					filtro_equipo_selected();
					//$j('.idc_'+idc).show();		
					$j('.loading_portal').hide();
					$j('#tabs_options').hide();
					/*if ((recarga==0) && (team_id>0)) {
						$j('.fila_stats_player').hide();
						setTimeout(function() {
							$j('.teamid_'+team_id).show('medium');					
						}, 100);

					}*/
					
					
					
					
				}
			}
		);

}


if (cliente!='cerilh') {
	if (cliente=='worldskate') {
		$j('#scorer_horizontal').load(ruta_files+cliente+'/'+cliente+'_mc_'+idm+'_horizontal.php');
		
		var sidgad_scorer = function() {
			var file_scorer = cliente+'_mc_'+idm+'.php';
			var sidgad_reload_scorer = setInterval(function() {	
				$j('#scorer_horizontal').load(ruta_files+cliente+'/'+cliente+'_mc_'+idm+'_horizontal.php');
				

				
				
			}, 30000);
		}	
		
		
		sidgad_scorer();		
		
		
		
	} else {
		
		
		$j('#scorer_competiciones').load(ruta_files+cliente+'/'+cliente+'_mc_'+idm+'.php',
			{
	
			},
			function( response, status, xhr ) {
				if (status == 'success') {
		
					var id_custom_club = $j("#id_custom_club").val();
					console.log("estamos dentro ..."+id_custom_club);
					if (id_custom_club>0) {
						//console.log("tenemos web de club");
						$j(".scorer_liga").show();
						$j(".scorer_game").hide();
						$j(".scorer_apartado").hide();
						$j("#scorer_competiciones .club_"+id_custom_club).show();
						
					} else {
						//console.log("NO tenemos web de club");
					}
	
					
				}
			}		
		);
		var sidgad_scorer = function() {
			var file_scorer = cliente+'_mc_'+idm+'.php';
			
			
			var sidgad_reload_scorer = setInterval(function() {	
				$j('#scorer_competiciones').load(ruta_files+cliente+'/'+cliente+'_mc_'+idm+'.php',
					{
			
					},
					function( response, status, xhr ) {
						if (status == 'success') {
				
							var id_custom_club = $j("#id_custom_club").val();
							console.log("estamos dentro ..."+id_custom_club);
							if (id_custom_club>0) {
								console.log("tenemos web de club");
								$j(".scorer_liga").show();
								$j(".scorer_game").hide();
								$j(".scorer_apartado").hide();
								$j("#scorer_competiciones .club_"+id_custom_club).show();
								
							} else {
								console.log("NO tenemos web de club");
							}
			
							
						}
					}		
				);

			}, 30000);
		}	
		
		
		sidgad_scorer();
	
	}
}


$j(document).on("click","#simpleidc_overview_btn",function(e){	
	e.preventDefault();
	$j('#tabs_options').hide();
	$j('.loading_portal').show();
	$j('.tab_modal_selected').removeClass('tab_modal_selected').addClass('tab_modal');
	$j(this).removeClass('tab_modal').addClass('tab_modal_selected');
	$j('#tab_modal_contenido_competicion').load(ruta_files+'/cerilh/overview.php',
		{

		},
		function( response, status, xhr ) {
			if (status == 'success') {
	
				$j('.loading_portal').hide();

				
			}
		}
	);	
	
	
});	
	
	
$j(document).on("click","#simpleidc_portada_btn",function(e){	
	e.preventDefault();
	$j('#tabs_options').show();
	$j('#menu_idc_options_general').hide();
	//file = cliente+"_"+file;
	var btn_id = $j(this).attr('id');
	var selected_menu = $j('#input_menu_selected').val();
	var filter = $j(this).attr('filter');
	var idc = $j('#idc').val();
	var tipo_stats = $j(this).attr('tipo_stats');
	$j('.tabla_standard').hide();
	$j('#filter').val(filter);
	$j('.tab_modal_selected').removeClass('tab_modal_selected').addClass('tab_modal');
	$j(this).removeClass('tab_modal').addClass('tab_modal_selected');

	$j('.loading_portal').show();
	$j('#input_menu_selected').val(btn_id);			
	var team_id = $j('#input_team_selected').val();
	$j('#tabs_options').show();
	$j('#plantilla_btn').hide();
	$j('#leaders_btn').show();
	$j('#menu_idc_options_stats').show();
	$j('.menu_competicion_btn_selected').removeClass('menu_competicion_btn_selected');
	$j('#leaders_btn').addClass('menu_competicion_btn_selected');
	$j('.menu_competicion_filters').hide();
	/*if (team_id>0) {
		filtro_equipo_selected();
	} else {*/
		var file = cliente+"_"+$j(this).attr('file');
		$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+file,
			{
				idc: 			idc,
				tipo_stats: 	tipo_stats,
				site_lang:		site_lang
			},
			function( response, status, xhr ) {
				if (status == 'success') {
					
					var team_id = $j('#input_team_selected').val();
					filtro_equipo_selected();
					//$j('.idc_'+idc).show();		
					$j('.lang_label').hide();
					$j('.lang_'+site_lang).show();	
					$j('.loading_portal').hide();
					
					
					
					
					
				}
			}
		);
});

$j(document).on("click","#simpleidc_games_btn",function(e){	
	e.preventDefault();
	//file = cliente+"_"+file;
	var btn_id = $j(this).attr('id');
	var selected_menu = $j('#input_menu_selected').val();
	var filter = $j(this).attr('filter');
	var idc = $j('#idc').val();
	var tipo_stats = $j(this).attr('tipo_stats');
	$j('.tabla_standard').hide();
	$j('#filter').val(filter);
	$j('.tab_modal_selected').removeClass('tab_modal_selected').addClass('tab_modal');
	$j(this).removeClass('tab_modal').addClass('tab_modal_selected');

	$j('.loading_portal').show();
	$j('#input_menu_selected').val(btn_id);			
	var team_id = $j('#input_team_selected').val();
	$j('#tabs_options').show();
	$j('#plantilla_btn').hide();
	$j('#menu_idc_options_stats').show();
	/*if (team_id>0) {
		filtro_equipo_selected();
	} else {*/
		var file = cliente+"_"+$j(this).attr('file');
		$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+file,
			{
				idc: 			idc,
				tipo_stats: 	tipo_stats,
				lang:			site_lang
			},
			function( response, status, xhr ) {
				if (status == 'success') {
					
					var team_id = $j('#input_team_selected').val();
					filtro_equipo_selected();
					//$j('.idc_'+idc).show();		
					$j('.loading_portal').hide();
					$j('#tabs_options').hide();
					/*if ((recarga==0) && (team_id>0)) {
						$j('.fila_stats_player').hide();
						setTimeout(function() {
							$j('.teamid_'+team_id).show('medium');					
						}, 100);

					}*/
					$j('.lang_label').hide();
					$j('.lang_'+site_lang).show();	
					
					
					
				}
			}
		);
});


$j(document).on("click","#simpleidc_rosters_btn",function(e){	
	e.preventDefault();
	$j('.menu_competicion_filters').show();
	$j('#menu_idc_options_general').hide();
	//file = cliente+"_"+file;
	var btn_id = $j(this).attr('id');
	var selected_menu = $j('#input_menu_selected').val();
	var filter = $j(this).attr('filter');
	var idc = $j('#idc').val();
	var tipo_stats = $j(this).attr('tipo_stats');
	$j('.tabla_standard').hide();
	$j('#filter').val(filter);
	$j('.tab_modal_selected').removeClass('tab_modal_selected').addClass('tab_modal');
	$j(this).removeClass('tab_modal').addClass('tab_modal_selected');

	$j('.loading_portal').show();
	$j('#input_menu_selected').val(btn_id);			
	var team_id = $j('#input_team_selected').val();
	$j('#tabs_options').show();
	$j('#menu_idc_options_stats').hide();
	$j('#plantilla_btn').click();
	
	if (team_id>0) {
		
	} else {

	}
	
});







$j(document).on("click",".game_report",function(e){	
	e.preventDefault();
	$j('#tab_selected_thickbox_big').val('tab_ficha_resumen');
	var idp = $j(this).attr('idp');
	$j('#idp_selected').val(idp);
	$j('#sidgad_thickbox_content').html('');
	var idc = $j('#idc').val();
	$j('.loading_portal').show();
	if (site_lang=='es') {
		$j('#sidgad_thickbox_topbar_content').text('FICHA DETALLE PARTIDO');
	}
	if (site_lang=='en') {
		$j('#sidgad_thickbox_topbar_content').text('GAME DETAIL');
	}	
	
	$j('#sidgad_thickbox').slideDown();
	$j('#sidgad_portal').hide();
	//reload_game_report();
	$j('#sidgad_thickbox_content').load(ruta_files+cliente+'/'+cliente+'_gr_'+idp+'_'+idm+'.php',
		{ 	idm:		idm,
			idc:		idc,
			idp:		idp,
			tab:		'tab_ficha_resumen',
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.loading_portal').hide();
				$j('.lang_label').hide();
				$j('.lang_'+site_lang).show();				
				
				var game_reload_web = function() {
					clearInterval(game_reload_web);
					var file_game_reload_web = ruta_files+cliente+'/'+cliente+'_gr_'+idp+'_'+idm+'.php';
					var sidgad_game_reload_web = setInterval(function() {
						var tab_selected = $j('#tab_selected_thickbox_big').val();
						if (tab_selected=='') { tab_selected = 'div_ficha_resumen'; }
						$j('#sidgad_thickbox_content').load(file_game_reload_web,
							{
							tab:		tab_selected,
							},
							function( response, status, xhr ) {
								if (status == 'success') {
									$j('#'+tab_selected).click();
									$j('.lang_label').hide();
									$j('.lang_'+site_lang).show();
									console.log("idioma en game_report: "+site_lang);
								}
							}
						);
					}, 30000);
				
					$j(document).on("click","#close_sidgad_thickbox",function(e){	
						e.preventDefault();
						clearInterval(sidgad_game_reload_web);
					});
					$j(document).on("click",".fa-search",function(e){	
						e.preventDefault();
						clearInterval(sidgad_game_reload_web);
					});				
				};			
				
				
				
				
				game_reload_web();
			}
		}
	);	
});	

$j(document).on("click",".listado_competiciones_fila__",function(e){	
	e.preventDefault();
	console.log('pulsando idc');
	$j('.loading_portal').show();
	var idc = $j(this).attr('id');
	//var file = cliente+"_"+$j(this).attr('portada_file');
	var acceso = $j(this).attr('acceso');
	$j('#idc').val(idc);
	$j('#titulo_competicion_header_text').html($j(this).attr('idc_name'));
	//if (cliente=='fpcyl') {
		$j('#titulo_competicion_subheader').html($j('#temp_selected_name').val());
	//}
	$j('#tabs_options').load(ruta_files+'competicion_header_creator.php',
		{ 	config_params:		$j(this).attr('config_params'),
			idm:				idm,
			teams_array:		$j('#teams_array_'+idc).val(),
			cliente:			cliente,
			temp:				$j('#temp').val(),
			idc:				idc,
			logo:				$j(this).attr('logo'),
			site_lang:			site_lang
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.lang_label').hide();
				$j('.lang_'+site_lang).show();
				
				$j('#tab_modal_contenido').slideUp();
				$j('#tab_modal_container').show();
				if (acceso=='calendario_btn') {
					$j('#portada_btn').hide();
				}
				if ($j("#overview").length) {
					$j('#simpleidc_overview_btn').click();
				} else {
					$j('#'+acceso).click();
				}
						
				window.history.pushState('page2', 'Title', "/league/"+idc);			
				

			}
		}	
	);

});	

$j(document).on("click",".listado_competiciones_fila___",function(e){	
	e.preventDefault();
	console.log('pulsando idc');
	$j('.loading_portal').show();
	var idc = $j(this).attr('id');
	//var file = cliente+"_"+$j(this).attr('portada_file');
	var acceso = $j(this).attr('acceso');
	$j('#idc').val(idc);
	$j('#titulo_competicion_header_text').html($j(this).attr('idc_name'));
	//if (cliente=='fpcyl') {
		$j('#titulo_competicion_subheader').html($j('#temp_selected_name').val());
	//}
	$j('#tabs_options').load(ruta_files+'competicion_header_creator.php',
		{ 	config_params:		$j(this).attr('config_params'),
			idm:				idm,
			teams_array:		$j('#teams_array_'+idc).val(),
			cliente:			cliente,
			temp:				$j('#temp').val(),
			idc:				idc,
			logo:				$j(this).attr('logo'),
			site_lang:			site_lang
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.lang_label').hide();
				$j('.lang_'+site_lang).show();
				
				$j('#tab_modal_contenido').slideUp();
				$j('#tab_modal_container').show();
				if (acceso=='calendario_btn') {
					$j('#portada_btn').hide();
				}
				if ($j("#overview").length) {
					$j('#simpleidc_overview_btn').click();
				} else {
					$j('#'+acceso).click();
				}
						
				window.history.pushState('page2', 'Title', "/"+site_lang+"_stats");			
				

			}
		}	
	);

});	

$j(document).on("click",".listado_competiciones_fila",function(e){	
	e.preventDefault();
	console.log('pulsando idc');
	$j('.loading_portal').show();
	var idc = $j(this).attr('id');
	//var file = cliente+"_"+$j(this).attr('portada_file');
	var acceso = $j(this).attr('acceso');
	$j('#idc').val(idc);
	$j('#titulo_competicion_header_text').html($j(this).attr('idc_name'));
	//if (cliente=='fpcyl') {
		$j('#titulo_competicion_subheader').html($j('#temp_selected_name').val());
	//}
	$j('#tabs_options').load(ruta_files+'competicion_header_creator.php',
		{ 	config_params:		$j(this).attr('config_params'),
			idm:				idm,
			teams_array:		$j('#teams_array_'+idc).val(),
			cliente:			cliente,
			temp:				$j('#temp').val(),
			idc:				idc,
			logo:				$j(this).attr('logo'),
			site_lang:			site_lang
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.lang_label').hide();
				$j('.lang_'+site_lang).show();
				$j('#tab_modal_contenido').slideUp();
				$j('#tab_modal_container').show();
				if (acceso=='calendario_btn') {
					$j('#portada_btn').hide();
				}
				if ($j("#overview").length) {
					$j('#simpleidc_overview_btn').click();
				} else {
					$j('#'+acceso).click();
				}
						
				window.history.pushState('page2', 'Title', "/league/"+idc);			

			}
		}	
	);

});	

$j(document).on("click",".menu_competicion_btn",function(e){	
	e.preventDefault();
	//clearInterval(sidgad_reload_sorteo);
	$j('.menu_competicion_filters').show();
	//file = cliente+"_"+file;
	var btn_id = $j(this).attr('id');
	var selected_menu = $j('#input_menu_selected').val();
	var filter = $j(this).attr('filter');
	var idc = $j('#idc').val();
	var tipo_stats = $j(this).attr('tipo_stats');
	$j('.tabla_standard').hide();
	$j('#filter').val(filter);
	$j('#leaders_btn').removeClass('menu_competicion_btn_selected');
	if (selected_menu == btn_id) {
		
		
		
		
	} else {
		
		$j('.loading_portal').show();
		$j('#'+selected_menu).removeClass('menu_competicion_btn_selected');
		$j('#'+btn_id).addClass('menu_competicion_btn_selected');
		$j('#input_menu_selected').val(btn_id);			
		var team_id = $j('#input_team_selected').val();
		
		
		var file = cliente+"_"+$j(this).attr('file');
		$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+file,
			{
				idc: 			idc,
				tipo_stats: 	tipo_stats,
				site_lang:		site_lang
			},
			function( response, status, xhr ) {
				if (status == 'success') {
					var team_id = $j('#input_team_selected').val();
					filtro_equipo_selected();
					$j('.lang_label').hide();
					$j('.lang_'+site_lang).show();		
					$j('.loading_portal').hide();
					$j('.lang_label').hide();
					$j('.lang_'+site_lang).show();
				}
			}
		);
		
		
		
			
			if (btn_id=='sorteo_btn') {
					//clearInterval(sidgad_reload_sorteo);
					var sidgad_sorteo = function() {
						var file_sorteo = $j('#sorteo_btn').attr('file');
						var sidgad_reload_sorteo = setInterval(function() {	
							$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+cliente+'_'+file_sorteo);
						}, 5000);
						$j(document).on("click","*",function(e){	
							clearInterval(sidgad_reload_sorteo);
						});	
					}	
					

					
					sidgad_sorteo();
			
			} 
			
		//} //no team_id
		
		
	}
	
	//console.log("pulsando_btn");
});

$j(document).on("click","#leaders_btn",function(e){	
	e.preventDefault();
	$j('.menu_competicion_filters').hide();	
});




$j(document).on("click","#show_copa_pruebas",function(e){	
	e.preventDefault();
	$j('.loading_portal').show();
	$j('#tab_modal_contenido_competicion').load(ruta_files+'/show_copa_pruebas.php',
		{
			idc: 			'25'
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.loading_portal').hide();
				
			}
		}
		);
});

$j(document).on("click",".logo_equipo_menu_container",function(e){
	var team_id = $j(this).attr('id');
	team_id = team_id.split('_');
	team_id = team_id[1];
	var selected_team_id = $j('#input_team_selected').val();
	
	if (selected_team_id == team_id) {
		$j('#teamid_'+team_id).removeClass('logo_equipo_menu_selected');
		$j('#input_team_selected').val('');
		
		
	} else {
		$j('.logo_equipo_menu_selected').removeClass('logo_equipo_menu_selected').addClass('logo_equipo_menu_container');
		$j('#teamid_'+team_id).addClass('logo_equipo_menu_selected');
		$j('#input_team_selected').val(team_id);

	}
	filtro_equipo_selected();
});


function sortTable() {
	/*
	var tbody = $j('#my_calendar_table tbody');
	
	tbody.find('tr').sort(function(a, b) {
	  var tda = $j(a).attr('gamedate'); // target order attribute
	  var tdb = $j(b).attr('gamedate'); // target order attribute
	  // if a < b return 1
	  return tda > tdb ? 1
	    // else if a > b return -1
	    : tda < tdb ? -1
	    // else they are equal - return 0    
	    : 0;
	}).appendTo(tbody);
	*/
  
	/*
	$j( "table tbody" ).sortable( {
		update: function( event, ui ) {
	    $j(this).children().each(function(index) {
				$j(this).attr("gamedate").html(index + 1)
	    });
	  }
	});
	
	
	$j("#my_calendar_table").append($j("tr").get().sort(function(a, b) {
        return parseInt($j(a).attr("gamedate")) - parseInt($j(b).attr("gamedate"))
    }));
    */
}


function filtro_equipo_selected	() {
	$j('.loading_portal').show();
	var team_id = $j('#input_team_selected').val();
	var selected_menu = $j('#input_menu_selected').val();
	var filter = $j('#filter').val();
	var idc = $j('#idc').val();
	if (team_id>0) {
		
		if (filter==1) {
			var file = cliente+"_"+$j('#'+selected_menu).attr('file_team');
			$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+file,
				{
					idc: idc,
					idq: $j('#input_team_selected').val()
				},
				function( response, status, xhr ) {
					if (status == 'success') {
						var team_id = $j('#input_team_selected').val();
						$j('.loading_portal').hide();
					}
				}
			);		
		}
		
		if (filter==2) {
			$j('.fila_stats_player').hide();
			setTimeout(function() {
				$j('.teamid_'+team_id).show('medium');					
			}, 100);		
		}	
		
		if (filter==3) {
			$j('.tabla_basic').show();
			$j('.leyenda_container').show();		
			$j('.fila_stats_player').hide();
			$j('.info_selec_team').hide();
			setTimeout(function() {
				$j('.teamid_'+team_id).show('medium');					
			}, 100);		
		}
		
		if (filter==4) {
			
			$j('.team_class').hide();
			$j('.head_jornada').hide();
			setTimeout(function() {
				$j('.team_'+team_id).show('medium');	
				$j('.jor_in_games').show('medium');		
				sortTable();	
				//$j("#my_calendar_table").tablesorter();		
			}, 100);						
		}
		
	} else {
		/*
		if (filter==1) {
			var file = cliente+"_"+$j('#'+selected_menu).attr('file');
			$j('#tab_modal_contenido_competicion').load(ruta_files+cliente+'/'+file,
				{
					idc: idc
				},
				function( response, status, xhr ) {
					if (status == 'success') {
						var team_id = $j('#input_team_selected').val();
						$j('.loading_portal').hide();
			
					}
				}
			);		
			
		}
		*/
		if (filter==2) {
			setTimeout(function() {
				$j('.fila_stats_player').show();				
			}, 100);		
		}
		if (filter==3) {
			$j('.fila_stats_player').hide();		
			if (site_lang=='es') {		
				$j('#tab_modal_contenido_competicion').prepend("<span class='info_selec_team'>SELECCIONE UN EQUIPO EN LA PARTE SUPERIOR PARA ACCEDER A SU PLANTILLA</span>");
			}
			if (site_lang=='en') {		
				$j('#tab_modal_contenido_competicion').prepend("<span class='info_selec_team'>YOU MUST SELECT A TEAM AT THE TOP BUTTONS</span>");
			}
			if (site_lang=='ca') {		
				$j('#tab_modal_contenido_competicion').prepend("<span class='info_selec_team'>SELECCIONEU UN EQUIP A LA PART SUPERIOR PER ACCEDIR A LA SEVA PLANTILLA</span>");
			}			
			
			
			
			
			$j('.tabla_basic').hide();	
			$j('.leyenda_container').hide();		
		}

		if (filter==4) {
			$j('.team_class').show();
			$j('.head_jornada').show();	
			$j('.jor_in_games').hide();			
		}		
		
	}
	
	/*var file_competicion = $j('#'+selected_menu).attr('file');
	var ruta_files = 'https://www.sidgad.com/shared/portales_files/3_0_2_competiciones_views/';
	$j('#tab_modal_contenido_competicion').load(ruta_files+file_competicion,
		{ 	hostcliente:	hostcliente,
			idc:			'<?php echo $idc;?>',
			idm:			'<?php echo $_POST['idm'];?>',
			team_id:		team_id
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.loading_portal').hide();
			}
		}
	);*/		
	$j('.loading_portal').hide();
}

$j(document).on("click",".volver_competiciones",function(e){	
	e.preventDefault();
	$j('#tab_modal_container').hide();	
	$j('#tab_modal_contenido').show();
	window.history.pushState('', '', "/");
});

	/*$j('#tabs_options').load(ruta_files+'competicion_header_creator.php',
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.loading_portal').hide();
			}
		}	
	);*/

$j(document).on("click",".player_season_stats",function(e){	
	//if (cliente == "fecapa" || cliente == "cap" || cliente == "rfep" || cliente == "fisr" || cliente == "fmp" || cliente=="worldskate") {
		
		e.preventDefault();
		var team_id = $j(this).attr('team_id');
		var id_player = $j(this).attr('id_player');
		var player_name = $j(this).attr('player_name');
		var temp_name = $j(this).attr('temp_name');
		var temp = $j('#temp').val();
		var idc = $j('#idc').val();
		$j('#sidgad_thickbox_right').show('medium');
		/*$j('#sidgad_thickbox_right_topbar_content').text('FICHA DETALLE - Temporada '+temp_name);*/
		$j('#sidgad_thickbox_right_content').show('medium');
		$j('.loading_thickbox_right').show();
		$j('#sidgad_thickbox_right_content').load(ruta_files+cliente+'/profiles/'+cliente+'_profileseason_'+id_player+'_'+idm+'_'+temp+'.php',
			{ 	idm:		 	idm,
				idc:		 	idc,
				id_player:		id_player,
				team_id:		team_id,
				temp_name:		temp_name
			},
			function( response, status, xhr ) {
				if (status == 'success') {
					$j('.loading_thickbox_right').hide();
					$j('.lang_label').hide();
					$j('.lang_'+site_lang).show();	
					$j('.loading_portal').hide();				
				} else if (status == 'error') { 
					console.log("tira un error");
				} 
			}
		);	
		
		
	/*} 
	else {

		e.preventDefault();
		var team_id = $j(this).attr('team_id');
		var id_player = $j(this).attr('id_player');
		var player_name = $j(this).attr('player_name');
		var temp_name = $j(this).attr('temp_name');
		var temp = $j('#temp').val();
		var idc = $j('#idc').val();
		$j('#sidgad_thickbox_right').show('medium');
		/*$j('#sidgad_thickbox_right_topbar_content').text('FICHA DETALLE - Temporada '+temp_name);*/
		/*$j('#sidgad_thickbox_right_content').show('medium');
		$j('.loading_thickbox_right').show();
		$j('#sidgad_thickbox_right_content').load(ruta_files+cliente+'/'+cliente+'_profileseason_'+idm+'_'+temp+'.php',
			{ 	idm:		 	idm,
				idc:		 	idc,
				id_player:		id_player,
				team_id:		team_id,
				temp_name:		temp_name
			},
			function( response, status, xhr ) {
				if (status == 'success') {
					$j('.loading_thickbox_right').hide();
					$j('.lang_label').hide();
					$j('.lang_'+site_lang).show();	
					$j('.loading_portal').hide();				
				}
			}
		);		
		
	}*/
	
	
});	

$j(document).on("click",".goalie_season_stats",function(e){	
	e.preventDefault();
	var team_id = $j(this).attr('team_id');
	var id_player = $j(this).attr('id_player');
	var player_name = $j(this).attr('player_name');
	var temp_name = $j(this).attr('temp_name');
	var idc = $j('#idc').val();
	var temp = $j('#temp').val();
	$j('#sidgad_thickbox_right').show('medium');
	$j('#sidgad_thickbox_right_topbar_content').text('FICHA DETALLE - Temporada '+temp_name);
	$j('#sidgad_thickbox_right_content').show('medium');
	$j('.loading_thickbox_right').show();
	$j('#sidgad_thickbox_right_content').load(ruta_files+cliente+'/'+cliente+'_goaliesprofileseason_'+idm+'_'+temp+'.php',
		{ 	idm:		 	idm,
			idc:		 	idc,
			id_player:		id_player,
			team_id:		team_id,
			temp_name:		temp_name
		},
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.loading_thickbox_right').hide();
			}
		}
	);			
});

$j(document).on("click",".video_partido",function(e){	
	e.preventDefault();
	var video_id = $j(this).attr('url_video');
	$j('#sidgad_thickbox_mini').show('medium');
	$j('#sidgad_thickbox_mini_content').html("<iframe width='640' height='360' src='https://www.youtube.com/embed/"+video_id+"?autoplay=1' frameborder='0' allowfullscreen></iframe>");			
});

$j(document).on("click",".video_partido_vimeo",function(e){	
	e.preventDefault();
	var video_id = $j(this).attr('url_video');
	$j('#sidgad_thickbox_mini').show('medium');
	$j('#sidgad_thickbox_mini_content').html("<iframe src='https://player.vimeo.com/video/"+video_id+"?title=0&byline=0&portrait=0' width='640' height='360' frameborder='0' webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>");			
});





$j(document).on("click","#close_sidgad_right_thickbox",function(e){	
	e.preventDefault();
	$j('#sidgad_thickbox_right').hide('medium');
});

$j(document).on("click","#close_sidgad_thickbox",function(e){	
	e.preventDefault();
	$j('#sidgad_thickbox').slideUp();
	$j('#sidgad_portal').show();
});

$j(document).on("click","#close_sidgad_thickbox_mini",function(e){	
	e.preventDefault();
	$j('#sidgad_thickbox_mini_content').html("");
	$j('#sidgad_thickbox_mini').hide();
});



$j(document).on("click",".tab_thickbox",function(e){
	e.preventDefault();
	$j('.tab_thickbox_selected').removeClass('tab_thickbox_selected');
	$j(this).addClass('tab_thickbox_selected');
	var div_show = $j(this).attr('div_show');
	$j('#tab_selected_thickbox_big').val($j(this).attr('id'));

	//$j('.thickbox_ficha_views').hide();
	//$j('#'+div_show).animate({width:'toggle'},350);
	
	$j('.thickbox_ficha_views').hide();
	$j('#'+div_show).show();
	
	/*$j('.thickbox_ficha_views').hide("slide", { direction: "right" }, 150);	

    setTimeout(function(){
		$j('#'+div_show).show("slide", { direction: "left" }, 300);	 
    }, 150);	*/	
});	

$j(document).on("click","#header_temp_selected",function(e){
	e.preventDefault();
	$j('#selector_temporadas').toggle();
});	
	
$j(document).on("click",".select_temporada",function(e){	
	$j('.loading_portal').show();
	e.preventDefault();
	var temp = $j(this).attr('id_temp');
	console.log("temporada seleccionada: "+temp);
	$j('#temp').attr('value',temp);
	//$j('#kkkk').val("12345");
	//$j('#kkkk').attr('value', '12345');
	var temp_name = $j(this).attr('temp_name');
	$j('#temp_selected_name').val(temp_name);
	$j('#selector_temporadas').hide();
	$j('#header_temp_selected').html(temp_name+'<i class="fa fa-sort" aria-hidden="true" style="padding-left: 10px; font-size: 14px;"></i>');
	$j('#listado_competiciones').load(ruta_files+cliente+'/'+cliente+'_ls_'+idm+'.php',
		function( response, status, xhr ) {
			if (status == 'success') {
				$j('.loading_portal').hide();
				$j('.temp_'+temp).show();
				
				
				
					var id_custom_club = $j("#id_custom_club").val();
					if (id_custom_club>0) {


						$j(".listado_competiciones_fila").hide();
						$j(".club_"+id_custom_club).show();
						
					}				

				
			}
			
			
		}	
	);
});



	
});