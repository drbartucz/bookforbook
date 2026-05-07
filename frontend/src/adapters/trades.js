function idEq(a, b) {
  return String(a) === String(b);
}

function isShippedStatus(status) {
  return status === "shipped" || status === "received";
}

function isReceivedStatus(status) {
  return status === "received";
}

function pickFirstNonNil(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null) {
      return value;
    }
  }
  return undefined;
}

function getParticipantId(participant, fallbackId) {
  if (participant && typeof participant === "object") {
    return pickFirstNonNil(participant.id, participant.user_id, participant.userId, participant.uuid, fallbackId);
  }
  return pickFirstNonNil(participant, fallbackId);
}

function normalizeParticipant(participant, fallbackId) {
  if (participant && typeof participant === "object") {
    return {
      ...participant,
      id: getParticipantId(participant, fallbackId),
    };
  }

  const id = getParticipantId(participant, fallbackId);
  return id ? { id } : null;
}

export function mapTradeForView(trade, currentUserId) {
  const shipments = Array.isArray(trade?.shipments) ? trade.shipments : [];

  const myOutgoing = currentUserId
    ? shipments.find((shipment) => idEq(
      getParticipantId(shipment?.sender, pickFirstNonNil(shipment?.sender_id, shipment?.senderId)),
      currentUserId
    ))
    : null;
  const myIncoming = currentUserId
    ? shipments.find((shipment) => idEq(
      getParticipantId(shipment?.receiver, pickFirstNonNil(shipment?.receiver_id, shipment?.receiverId)),
      currentUserId
    ))
    : null;

  const outgoingReceiver = normalizeParticipant(
    myOutgoing?.receiver,
    pickFirstNonNil(myOutgoing?.receiver_id, myOutgoing?.receiverId)
  );
  const incomingSender = normalizeParticipant(
    myIncoming?.sender,
    pickFirstNonNil(myIncoming?.sender_id, myIncoming?.senderId)
  );

  const partner =
    trade?.partner ??
    trade?.other_user ??
    outgoingReceiver ??
    incomingSender ??
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
    myShipped: myOutgoing
      ? isShippedStatus(myOutgoing.status)
      : Boolean(pickFirstNonNil(trade?.my_shipped, trade?.myShipped)),
    myShippedAt: pickFirstNonNil(myOutgoing?.shipped_at, myOutgoing?.shippedAt, trade?.my_shipped_at, trade?.myShippedAt) ?? null,
    myTracking: pickFirstNonNil(myOutgoing?.tracking_number, myOutgoing?.trackingNumber, myOutgoing?.tracking, trade?.my_tracking, trade?.myTracking) ?? "",
    iReceived: myIncoming
      ? isReceivedStatus(myIncoming.status)
      : Boolean(pickFirstNonNil(trade?.i_received, trade?.iReceived)),
    theyShipped: myIncoming
      ? isShippedStatus(myIncoming.status)
      : Boolean(pickFirstNonNil(trade?.they_shipped, trade?.theyShipped)),
    theyShippedAt: pickFirstNonNil(myIncoming?.shipped_at, myIncoming?.shippedAt, trade?.they_shipped_at, trade?.theyShippedAt) ?? null,
    theirTracking: pickFirstNonNil(myIncoming?.tracking_number, myIncoming?.trackingNumber, myIncoming?.tracking, trade?.their_tracking, trade?.theirTracking) ?? "",
    theyReceived: myOutgoing
      ? isReceivedStatus(myOutgoing.status)
      : Boolean(pickFirstNonNil(trade?.they_received, trade?.theyReceived)),
    iRated: Boolean(pickFirstNonNil(trade?.i_rated, trade?.iRated)),
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
