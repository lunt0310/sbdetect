<script>
	export default {
		onLaunch: function() {},
		onShow: function() {},
		onHide: function() {}
	}
</script>

<style>
	page {
		background: #f2f2f2;
		color: #111111;
		font-size: 28rpx;
	}

	view,
	text,
	button,
	input,
	picker,
	image,
	scroll-view {
		box-sizing: border-box;
	}

	button {
		margin: 0;
		padding: 0;
		border: none;
		background: transparent;
		line-height: 1;
	}

	button::after {
		border: none;
	}

	input {
		min-height: 44px;
	}
</style>

