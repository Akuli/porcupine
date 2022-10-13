fn filter_and_mutate_all_squares_in_place<F>(&mut self, mut f: F)
where
    F: for<'a> FnMut(WorldPoint, &'a mut SquareContent, Option<usize>) -> bool,
{
}
