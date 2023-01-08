$(document).ready(function() {
	$.getJSON('config.json', function(config_json) {
		console.log(config_json);

		var $anim = $('#animation');
		$anim.empty().append(function() {
			var options = '';
			$.each(config_json, function(key, value) {
				if (key != 'current_animation') {
					options += '<option>' + key + '</option>';
				}
			});
			return options;
		});
		$anim.change(function(event) {
			console.log('new selected value:', $anim.val());
			config_json['current_animation'] = $anim.val();
			$.ajax('post_config.php', {
				data: JSON.stringify(config_json),
				contentType: 'application/json',
				type: 'POST',
				success: function(response) {
					console.log('post response = ', response);
					if (!!response['success']) {
						console.log('Config updated successfully');
					}
					else {
						console.error('Error updating config: ', response);
					}
				},
				error: function(xhr, error, ex) {
					console.error('Error posting config: ' + error + ': ' + ex);
				}
			});
		});
		var current_animation = config_json['current_animation'];
		if (current_animation !== undefined) {
			$anim.val(current_animation);
		}

		// TODO render form to edit config values

	});
});
