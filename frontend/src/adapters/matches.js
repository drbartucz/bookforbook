function idEq(a, b) {
  return String(a) === String(b);
}

export function mapMatchForCard(match, currentUserId) {
  const legs = Array.isArray(match?.legs) ? match.legs : [];

  const outgoingLeg = currentUserId
    ? legs.find((leg) => idEq(leg?.sender?.id, currentUserId))
    : null;
  const incomingLeg = currentUserId
    ? legs.find((leg) => idEq(leg?.receiver?.id, currentUserId))
    : null;

  const yourBook = outgoingLeg?.user_book?.book ?? match?.your_book?.book ?? match?.offered_book?.book ?? null;
  const theirBook = incomingLeg?.user_book?.book ?? match?.their_book?.book ?? match?.requested_book?.book ?? null;

  const partner =
    match?.partner ??
    match?.other_user ??
    outgoingLeg?.receiver ??
    incomingLeg?.sender ??
    null;

  return {
    ...match,
    yourBook,
    yourCondition: outgoingLeg?.user_book?.condition ?? match?.your_book?.condition ?? null,
    theirBook,
    theirCondition: incomingLeg?.user_book?.condition ?? match?.their_book?.condition ?? null,
    partner,
  };
}
