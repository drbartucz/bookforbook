function idEq(a, b) {
  return String(a) === String(b);
}

function isShippedStatus(status) {
  return status === "shipped" || status === "received";
}

function isReceivedStatus(status) {
  return status === "received";
}

export function mapTradeForView(trade, currentUserId) {
  const shipments = Array.isArray(trade?.shipments) ? trade.shipments : [];

  const myOutgoing = currentUserId
    ? shipments.find((shipment) => idEq(shipment?.sender?.id, currentUserId))
    : null;
  const myIncoming = currentUserId
    ? shipments.find((shipment) => idEq(shipment?.receiver?.id, currentUserId))
    : null;

  const partner =
    trade?.partner ??
    trade?.other_user ??
    myOutgoing?.receiver ??
    myIncoming?.sender ??
    null;

  const partnerAddressRaw = partner?.id
    ? trade?.partner_addresses?.[String(partner.id)] ?? null
    : null;

  const partnerAddress = partnerAddressRaw
    ? {
        name: partnerAddressRaw.full_name || partnerAddressRaw.institution_name || "",
        street: partnerAddressRaw.address_line_1 || "",
        street2: partnerAddressRaw.address_line_2 || "",
        city: partnerAddressRaw.city || "",
        state: partnerAddressRaw.state || "",
        zip: partnerAddressRaw.zip_code || "",
      }
    : null;

  const myBook = myOutgoing?.user_book ?? trade?.my_book ?? trade?.initiator_book ?? null;
  const theirBook = myIncoming?.user_book ?? trade?.their_book ?? trade?.responder_book ?? null;

  return {
    ...trade,
    myOutgoing,
    myIncoming,
    myBook,
    theirBook,
    partner,
    partnerAddress,
    myShipped: myOutgoing ? isShippedStatus(myOutgoing.status) : Boolean(trade?.my_shipped),
    myShippedAt: myOutgoing?.shipped_at ?? trade?.my_shipped_at ?? null,
    myTracking: myOutgoing?.tracking_number ?? trade?.my_tracking ?? "",
    iReceived: myIncoming ? isReceivedStatus(myIncoming.status) : Boolean(trade?.i_received),
    theyShipped: myIncoming ? isShippedStatus(myIncoming.status) : Boolean(trade?.they_shipped),
    theyShippedAt: myIncoming?.shipped_at ?? trade?.they_shipped_at ?? null,
    theirTracking: myIncoming?.tracking_number ?? trade?.their_tracking ?? "",
    theyReceived: myOutgoing ? isReceivedStatus(myOutgoing.status) : Boolean(trade?.they_received),
    iRated: Boolean(trade?.i_rated),
  };
}

export function buildTradeRatingPayload(tradeView, formState) {
  if (!tradeView?.partner?.id) return null;

  return {
    rated_user_id: tradeView.partner.id,
    score: formState.score,
    comment: formState.comment ?? "",
    book_condition_accurate: Boolean(formState.bookConditionAccurate),
  };
}
