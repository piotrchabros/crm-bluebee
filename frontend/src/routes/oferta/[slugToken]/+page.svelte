<script>
  import '$lib/offer/offer.css';
  import Offer from '$lib/offer/Offer.svelte';

  /** @type {{ data: { offer: any } }} */
  let { data } = $props();
</script>

<svelte:head>
  <title>{data.offer?.title || 'Oferta'} · {data.offer?.client_name || ''}</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<Offer offer={data.offer} />
