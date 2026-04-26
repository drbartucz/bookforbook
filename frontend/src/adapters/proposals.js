function idEq(a, b) {
  return String(a) === String(b);
}

function getProposalItems(proposal) {
  if (!Array.isArray(proposal?.items)) {
    return {
      proposerSends: null,
      recipientSends: null,
    };
  }

  return {
    proposerSends:
      proposal.items.find((item) => item?.direction === "proposer_sends") ?? null,
    recipientSends:
      proposal.items.find((item) => item?.direction === "recipient_sends") ?? null,
  };
}

export function mapProposalForCard(proposal, currentUserId) {
  const { proposerSends, recipientSends } = getProposalItems(proposal);
  const isMine = idEq(proposal?.proposer?.id, currentUserId);

  const offered = proposerSends?.user_book ?? proposal?.offered_book ?? null;
  const requested = recipientSends?.user_book ?? proposal?.requested_book ?? null;

  return {
    ...proposal,
    offeredBook: offered?.book ?? offered,
    offeredCondition: offered?.condition ?? null,
    requestedBook: requested?.book ?? requested,
    requestedCondition: requested?.condition ?? null,
    note: proposal?.message ?? proposal?.note ?? "",
    isMine,
  };
}
